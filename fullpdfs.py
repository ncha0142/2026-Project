import argparse
import sys
import os
import csv
import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
import multiprocessing as mp

parser = argparse.ArgumentParser()
parser._optionals.title = "Flag Arguments"
parser.add_argument('-pmids', help="Comma separated list of pmids to fetch. Must include -pmids or -pmf.", default='%#$')
parser.add_argument('-pmf', help="File with pmids to fetch inside. Must include -pmids or -pmf", default='%#$')
parser.add_argument('-out', help="Output directory for fetched articles. Default: fetched_pdfs", default="fetched_pdfs")
parser.add_argument('-maxRetries', help="Change max number of retries per article. Default: 3", default=3, type=int)

def getMainUrl(url):
    return "/".join(url.split("/")[:3])

def savePdfFromUrl(pdfUrl, directory, name, headers):
    t = requests.get(pdfUrl, headers=headers, allow_redirects=True, timeout=30)
    t.raise_for_status()
    content_type = t.headers.get('Content-Type', '').lower()
    if 'application/pdf' not in content_type and not t.content.startswith(b'%PDF'):
        raise ValueError("Downloaded content is not a PDF")
    with open('{0}/{1}.pdf'.format(directory, name), 'wb') as f:
        f.write(t.content)

def isFreeFullText(req, soup):
    url = req.url.lower()
    content_type = req.headers.get('Content-Type', '').lower()

    if 'application/pdf' in content_type or req.content.startswith(b'%PDF'):
        return True

    if '/pmc/articles/' in url:
        return True

    if 'pubmed.ncbi.nlm.nih.gov' in url or 'eutils.ncbi.nlm.nih.gov' in url or re.search(r'ncbi\.nlm\.nih\.gov/pubmed', url):
        return False

    if content_type and 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
        return False

    text = soup.get_text(" ", strip=True).lower()[:10000]
    blocked_patterns = [
        'purchase this article',
        'buy this article',
        'rent this article',
        'subscribe to continue',
        'access through your institution',
        'institutional access',
        'sign in to access',
        'login to access',
        'log in to access',
        'get access',
        'check access',
        'request permissions',
        'article not available',
        'abstract only'
    ]

    for pattern in blocked_patterns:
        if pattern in text:
            return False

    return True

def fetchPage(url, headers):
    req = requests.get(url, headers=headers, allow_redirects=True, timeout=30)
    soup = BeautifulSoup(req.content, 'lxml')
    return req, soup

def tryPdfFinders(req, soup, headers, finders, out_dir, name):
    for finder in finders:
        pdfUrl = globals()[finder](req, soup, headers)
        if pdfUrl is not None:
            savePdfFromUrl(pdfUrl, out_dir, name, headers)
            return True, pdfUrl
    return False, None

def fetch(pmid, finders, name, headers, out_dir):
    uri = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=pubmed&id={0}&retmode=ref&cmd=prlinks".format(pmid)

    result = {
        'pmid': pmid,
        'status': 'failed',
        'final_url': '',
        'full_text_found': 'no',
        'pdf_downloaded': 'no',
        'pdf_url': '',
        'note': ''
    }

    if os.path.exists("{0}/{1}.pdf".format(out_dir, pmid)):
        result['status'] = 'existing_pdf'
        result['pdf_downloaded'] = 'yes'
        result['full_text_found'] = 'yes'
        result['note'] = 'PDF already downloaded'
        print("** Reprint #{0} already downloaded; skipping.".format(pmid))
        return result

    req, soup = fetchPage(uri, headers)
    result['final_url'] = req.url

    if 'ovid' in req.url.lower():
        result['status'] = 'unsupported'
        result['note'] = 'ovid not supported'
        print("** Reprint {0} cannot be fetched (ovid not supported).".format(pmid))
        return result

    if isFreeFullText(req, soup):
        result['full_text_found'] = 'yes'
        result['status'] = 'full_text_found'

    pdf_success, pdf_url = tryPdfFinders(req, soup, headers, finders, out_dir, name)
    if pdf_success:
        result['pdf_downloaded'] = 'yes'
        result['pdf_url'] = pdf_url
        result['status'] = 'pdf_downloaded'
        print("** fetching of reprint {0} succeeded".format(pmid))
        return result

    pmc_article_url = pubmed_central_v2(req, soup, headers)
    if pmc_article_url is not None:
        pmc_req, pmc_soup = fetchPage(pmc_article_url, headers)
        result['final_url'] = pmc_req.url

        if isFreeFullText(pmc_req, pmc_soup):
            result['full_text_found'] = 'yes'
            if result['status'] == 'failed':
                result['status'] = 'full_text_found'

        pdf_success, pdf_url = tryPdfFinders(pmc_req, pmc_soup, headers, finders, out_dir, name)
        if pdf_success:
            result['pdf_downloaded'] = 'yes'
            result['pdf_url'] = pdf_url
            result['status'] = 'pdf_downloaded'
            print("** fetching of reprint {0} succeeded".format(pmid))
            return result

    if result['full_text_found'] == 'yes':
        print("** full text found for reprint {0}, but no PDF downloaded".format(pmid))
    else:
        print("** Reprint {0} could not be fetched with the current finders.".format(pmid))

    return result

def acsPublications(req, soup, headers):
    possibleLinks = [x for x in soup.find_all('a') if type(x.get('title')) == str and ('high-res pdf' in x.get('title').lower() or 'low-res pdf' in x.get('title').lower())]
    if len(possibleLinks) > 0:
        return urllib.parse.urljoin(req.url, possibleLinks[0].get('href'))
    return None

def direct_pdf_link(req, soup, headers):
    content_type = req.headers.get('Content-Type', '').lower()
    if 'application/pdf' in content_type or req.url.lower().endswith('.pdf'):
        return req.url
    return None

def futureMedicine(req, soup, headers):
    possibleLinks = soup.find_all('a', attrs={'href': re.compile("/doi/pdf")})
    if len(possibleLinks) > 0:
        return urllib.parse.urljoin(req.url, possibleLinks[0].get('href'))
    return None

def genericCitationLabelled(req, soup, headers):
    possibleLinks = soup.find_all('meta', attrs={'name': 'citation_pdf_url'})
    if len(possibleLinks) > 0:
        return possibleLinks[0].get('content')
    return None

def nejm(req, soup, headers):
    possibleLinks = [x for x in soup.find_all('a') if type(x.get('data-download-type')) == str and (x.get('data-download-type').lower() == 'article pdf')]
    if len(possibleLinks) > 0:
        return urllib.parse.urljoin(req.url, possibleLinks[0].get('href'))
    return None

def pubmed_central_v1(req, soup, headers):
    possibleLinks = soup.find_all('meta', attrs={'name': 'citation_pdf_url'})
    if len(possibleLinks) > 0:
        return possibleLinks[0].get('content')
    possibleLinks = [x for x in soup.find_all('a', href=True) if re.search(r'/articles/.+?/pdf', x.get('href'))]
    if len(possibleLinks) > 0:
        return urllib.parse.urljoin(req.url, possibleLinks[0].get('href'))
    return None

def pubmed_central_v2(req, soup, headers):
    possibleLinks = soup.find_all('a', attrs={'href': re.compile('/pmc/articles')})
    if len(possibleLinks) > 0:
        return urllib.parse.urljoin("https://www.ncbi.nlm.nih.gov", possibleLinks[0].get('href'))
    return None

def science_direct(req, soup, headers):
    try:
        newUri = urllib.parse.unquote(soup.find_all('input')[0].get('value'))
        req = requests.get(newUri, allow_redirects=True, headers=headers, timeout=30)
        soup = BeautifulSoup(req.content, 'lxml')
        possibleLinks = soup.find_all('meta', attrs={'name': 'citation_pdf_url'})
        if len(possibleLinks) > 0:
            return possibleLinks[0].get('content')
    except:
        pass
    return None

def uchicagoPress(req, soup, headers):
    possibleLinks = [x for x in soup.find_all('a') if type(x.get('href')) == str and 'pdf' in x.get('href') and '.edu/doi/' in x.get('href')]
    if len(possibleLinks) > 0:
        return urllib.parse.urljoin(req.url, possibleLinks[0].get('href'))
    return None

def main(pmid, max_retries, out_dir):
    print("Starting:", pmid)
    name = pmid
    finders = ['genericCitationLabelled', 'pubmed_central_v1', 'acsPublications', 'uchicagoPress', 'nejm', 'futureMedicine', 'science_direct', 'direct_pdf_link']
    headers = requests.utils.default_headers()
    headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

    retriesSoFar = 0
    while retriesSoFar < max_retries:
        try:
            return fetch(pmid, finders, name, headers, out_dir)
        except Exception as e:
            retriesSoFar += 1
            if retriesSoFar >= max_retries:
                print("** fetching of reprint {0} failed: {1}".format(pmid, e))
                return {
                    'pmid': pmid,
                    'status': 'failed',
                    'final_url': '',
                    'full_text_found': 'no',
                    'pdf_downloaded': 'no',
                    'pdf_url': '',
                    'note': str(e)
                }

if __name__ == "__main__":
    args = vars(parser.parse_args())

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if args['pmids'] == '%#$' and args['pmf'] == '%#$':
        print("Error: Either -pmids or -pmf must be used. Exiting.")
        sys.exit(1)

    if not os.path.exists(args['out']):
        os.makedirs(args['out'])

    if args['pmids'] != '%#$':
        pmids = args['pmids'].split(",")
    else:
        pmids = [line.strip().split()[0] for line in open(args['pmf']) if line.strip()]

    total = len(pmids)
    print("Total number of PMIDS:", total)

    worker_args = [(p, args['maxRetries'], args['out']) for p in pmids]
    num_workers = max(1, min(4, mp.cpu_count() - 1))

    with mp.Pool(num_workers) as pool:
        results = pool.starmap(main, worker_args)

    report_path = os.path.join(args['out'], 'fetch_report.csv')
    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['pmid', 'status', 'final_url', 'full_text_found', 'pdf_downloaded', 'pdf_url', 'note'])
        writer.writeheader()
        writer.writerows(results)

    pdf_count = sum(1 for r in results if r['pdf_downloaded'] == 'yes')
    full_text_count = sum(1 for r in results if r['full_text_found'] == 'yes')

    print("Full texts found:", full_text_count)
    print("PDFs downloaded:", pdf_count)
    print("Report written to:", report_path)
    print("End")