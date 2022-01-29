"""
    Format the json data to tsv.
"""

import json
import os
from multiprocessing import Pool

def persist(file_name, data_lines):
    cols = ["isbn", 'series', "format", "authors", "publisher", "num_pages", "similar_books", "country_code",
            "language_code", "publication_year", "book_id", "work_id", "title", "title_without_series"]

    split = file_name.split("/")
    dir, file = "/".join(split[:-1]), split[-1].split("_")[-1].split(".")[0]
    format = "tsv"

    new_file_name = os.path.join(dir, f"{file}.{format}")

    with open(new_file_name, "w") as fout:
        fout.write("\t".join(cols) + "\n")
        for line in data_lines:
            if line:
                fout.write(line)


def persistauth(file_name, data_lines):
    cols = ["author_id", "name"]

    split = file_name.split("/")
    dir, file = "/".join(split[:-1]), split[-1].split("_")[-1].split(".")[0]
    format = "tsv"

    new_file_name = os.path.join(dir, f"{file}.{format}")

    with open(new_file_name, "w") as fout:
        fout.write("\t".join(cols) + "\n")
        for line in data_lines:
            if line:
                fout.write(line)


def persistwork(file_name, data_lines):
    cols = ["original_publication_year", "work_id", "original_title"]

    split = file_name.split("/")
    dir, file = "/".join(split[:-1]), split[-1].split("_")[-1].split(".")[0]
    format = "tsv"

    new_file_name = os.path.join(dir, f"{file}.{format}")

    with open(new_file_name, "w") as fout:
        fout.write("\t".join(cols) + "\n")
        for line in data_lines:
            if line:
                fout.write(line)


def persisseries(file_name, data_lines):
    cols = ["series_id", "series_works_count", "primary_work_count", "title"]

    split = file_name.split("/")
    dir, file = "/".join(split[:-1]), split[-1].split("_")[-1].split(".")[0]
    format = "tsv"

    new_file_name = os.path.join(dir, f"{file}.{format}")

    with open(new_file_name, "w") as fout:
        fout.write("\t".join(cols) + "\n")
        for line in data_lines:
            if line:
                fout.write(line)


def persissgenres(file_name, data_lines):
    cols = ["book_id", "genres"]

    split = file_name.split("/")
    dir, file = "/".join(split[:-1]), split[-1].split("_")[-1].split(".")[0]
    format = "tsv"

    new_file_name = os.path.join(dir, f"{file}.{format}")

    with open(new_file_name, "w") as fout:
        fout.write("\t".join(cols) + "\n")
        for line in data_lines:
            if line:
                fout.write(line)

def process(line):
    cols = ["isbn", 'series', "format", "authors", "publisher", "num_pages", "similar_books", "country_code",
            "language_code", "publication_year", "book_id", "work_id", "title", "title_without_series"]
    book = []
    jsn = json.loads(line)

    for category in cols:
        value = jsn[category]

        if category == "language_code" and not jsn[category].startswith("en"):
            break 
        
        if category == "authors":
            value = " ".join([x["author_id"] for x in jsn[category]])
        elif category == "series":
            value = " ".join(value)
        elif category == "similar_books":
            value = " ".join(value)
        elif category == "genres":
            value = " ".join(value.keys())
        elif category in  ["format", "publisher", "country_code","language_code", "title", "title_without_series"]:
            value = ' '.join(value.split())
            # process alphanumeric
            # value = " ".join("".join([x for x in s if x.isalnum() or x == " "]).split())
            
        if value:
            book.append(value)
        else:
            book.append("")

    return '\t'.join(book) + "\n"

def processauth(line):
    cols = ["author_id", "name"]
    book = []
    jsn = json.loads(line)

    for category in cols:
        value = jsn[category]

        if category == "name":
            value = ' '.join(value.split())

        if value:
            book.append(value)
        else:
            book.append("")

    return '\t'.join(book) + "\n"


def processwork(line):
    cols = ["original_publication_year", "work_id", "original_title"]
    book = []
    jsn = json.loads(line)

    for category in cols:
        value = jsn[category]

        if category == "original_title":
            value = ' '.join(value.split())

        if value:
            book.append(value)
        else:
            book.append("")

    return '\t'.join(book) + "\n"


def processseries(line):
    cols = ["series_id", "series_works_count", "primary_work_count", "title"]
    book = []
    jsn = json.loads(line)

    for category in cols:
        value = jsn[category]

        if category == "title":
            value = ' '.join(value.split())
        if value:
            book.append(value)
        else:
            book.append("")

    return '\t'.join(book) + "\n"


def processgenres(line):
    cols = ["book_id", "genres"]
    book = []
    jsn = json.loads(line)

    for category in cols:
        value = jsn[category]

        if category == "genres":
            value = " ".join(jsn[category].keys())

        if value:
            book.append(value)
        else:
            book.append("")

    return '\t'.join(book) + "\n"


if __name__ == "__main__":
    pool = Pool()
    # lines = process_data(os.path.abspath("data/goodreads_books.json"), cols)
    print("Starting the process...")

    file_name = "data/goodreads_books.json"
    data_lines = pool.map(process, open(os.path.abspath(file_name), "r").readlines())
    persist(file_name, data_lines)

    # authpath = 'data/goodreads_book_authors.json'
    # authdata = pool.map(processauth, open(os.path.abspath(authpath), "r").readlines())
    # persistauth(authpath, authdata)

    # workpath = 'data/goodreads_book_works.json'
    # workdata = pool.map(processwork, open(os.path.abspath(workpath), "r").readlines())
    # persistwork(workpath, workdata)

    # seriespath = 'data/goodreads_book_series.json'
    # seriesdata = pool.map(processseries, open(os.path.abspath(seriespath), "r").readlines())
    # persisseries(seriespath, seriesdata)

    # genrespath = 'data/goodreads_book_genres_initial.json'
    # genresdata = pool.map(processgenres, open(os.path.abspath(genrespath), "r").readlines())
    # persissgenres(genrespath, genresdata)

    pool.close()
