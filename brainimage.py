import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from wordcloud import WordCloud
from collections import Counter

def wc(combined, location):
    total = Counter(combined).most_common()

    brain_mask = np.array(Image.open("head.png"))

    dict_for_wc = dict(total)
    wordcloud = WordCloud(
        background_color="white",
        colormap="plasma",
        mask=brain_mask,
        contour_width=3,
        contour_color='firebrick'
    ).generate_from_frequencies(dict_for_wc)

    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    wordcloud.to_file('{}freq_WordCloud.png'.format(location))

total_counts = [
    ('lateral', 44622),
    ('thalamus', 42336),
    ('temporal', 25990),
    ('frontal', 24752),
    ('posterior', 8847),
    ('motor', 8483),
    ('anterior', 8176),
    ('medial', 7254),
    ('superior', 7128),
    ('parietal', 6860),
    ('middle', 6448),
    ('nucleus', 5583),
    ('occipital', 5253),
    ('inferior', 3852),
    ('supplementary', 3714),
    ('cingulate', 3324),
    ('location', 2209),
    ('ventral', 1845),
    ('orbital', 1710),
    ('cerebellum', 1433),
    ('insula', 1164),
    ('cuneus', 805),
    ('hippocampus', 787),
    ('pole', 736),
    ('precuneus', 727),
    ('olfactory', 664),
    ('amygdala', 599),
    ('crus', 509),
    ('pars', 451),
    ('reticular', 395),
    ('lingual', 378),
    ('caudate', 366),
    ('angular ', 209),
    ('precentral', 198),
    ('pulvinar', 196),
    ('fusiform', 134),
    ('postcentral', 126),
    ('parahippocampal', 125),
    ('pallidum', 97),
    ('vermis', 84),
    ('supramarginal', 84),
    ('rectus', 78),
    ('intralaminar', 74),
    ('mediodorsal', 66),
    ('rolandic', 63),
    ('geniculate', 58),
    ('calcarine', 55),
    ('paracentral', 51),
    ('heschl', 44),
    ('posterolateral', 43),
    ('putamen', 16),
    ('magnocellular', 10),
    ('parvocellular', 3),
    ('orbitalis', 3),
    ('anteroventral', 2),
    ('limitans', 1)
]

combined = []
for word, count in total_counts:
    combined.extend([word] * count)

location = input("Please enter the Path to directory where outputs should be saved. \n ie: C:/Users/noahj/Downloads/ \n Path: ")

wc(combined, location)

print("Saved to: {}freq_WordCloud.png".format(location))