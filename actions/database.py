import sqlite3
import argparse
import pathlib
import csv
import time 

import search 

def create_tables(c):
    print("-- CREATING TABLES -- ")
    # c.execute("DROP TABLE users")
    ### USER ###
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER NOT NULL PRIMARY KEY,
        user_first_name TEXT NOT NULL,
        user_last_name TEXT NOT NULL
        )""")

    c.execute("""CREATE TABLE IF NOT EXISTS user_book (
        user_id INTEGER,
        book_id INTEGER,
        return_date INTEGER,
        is_returned BOOLEAN NOT NULL CHECK (is_returned IN (0, 1)),
        FOREIGN KEY(book_id) REFERENCES book_info(book_id),
        FOREIGN KEY(user_id) REFERENCES user(user_id)
        )""")

    ### BOOK ###
    c.execute("""CREATE TABLE IF NOT EXISTS book_info (
        isbn    TEXT,
        format  TEXT,
        publisher   TEXT,
        num_pages   INTEGER,
        country_code    TEXT,
        language_code   TEXT,
        publication_year    INTEGER,
        book_id INTEGER NOT NULL PRIMARY KEY, 
        work_id INTEGER,
        is_available BOOLEAN NOT NULL CHECK (is_available IN (0, 1)),
        FOREIGN KEY(work_id) REFERENCES works(work_id)
        )""")

    c.execute("""CREATE TABLE IF NOT EXISTS book_series (
        book_id INTEGER,
        series_id INTEGER,
        FOREIGN KEY(book_id) REFERENCES book_info(book_id),
        FOREIGN KEY(series_id) REFERENCES series(series_id)
        )""")

    c.execute("""CREATE TABLE IF NOT EXISTS book_authors (
        book_id INTEGER,
        author_id INTEGER,
        FOREIGN KEY(book_id) REFERENCES book_info(book_id),
        FOREIGN KEY(author_id) REFERENCES authors(author_id)
        )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS book_similar_books (
        book_id INTEGER,
        similar_book_id INTEGER,
        FOREIGN KEY(book_id) REFERENCES book_info(book_id),
        FOREIGN KEY(similar_book_id) REFERENCES authors(book_id)
        )""")

    ### SERIES ###
    c.execute("""CREATE TABLE IF NOT EXISTS series (
        series_id INTEGER NOT NULL PRIMARY KEY,
        series_works_count INTEGER,
        primary_work_count INTEGER, 
        title TEXT
        )""")
    
    ### WORKS ###
    c.execute("""CREATE TABLE IF NOT EXISTS works (
        original_publication_year INTEGER,
        work_id INTEGER NOT NULL PRIMARY KEY,
        original_title TEXT
        )""")

    ### GENRES ###
    c.execute("""CREATE TABLE IF NOT EXISTS genres (
        book_id INTEGER, 
        genre TEXT,
        FOREIGN KEY(book_id) REFERENCES book_info(book_id)
        )""")

def print_tables(c):
    pirnt(" -- PRING TABLES -- ")

    c.execute("""SELECT * FROM user_book""")
    # c.execute("""SELECT * FROM book_info""")
    rows = c.fetchall()
    for row in rows:
        print(row)
    
    c.execute("""SELECT * FROM book_info  WHERE book_id=1""")
    print("table book_info:")
    rows = c.fetchone()
    print(rows)

    c.execute("""SELECT * FROM book_series""")
    print("table book_series:")
    rows = c.fetchall()
    for row in rows:
        print(row)

    c.execute("""SELECT * FROM book_authors""")
    print("table book_authors:")
    rows = c.fetchall()
    for row in rows:
        print(row)

    c.execute("""SELECT * FROM book_similar_books""")
    print("table book_similar_books:")
    rows = c.fetchall()
    for row in rows:
        print(row)

    c.execute("""SELECT * FROM authors""")
    print("table author:")
    rows = c.fetchall()
    for row in rows:
        print(row)
    
    c.execute("""SELECT * FROM series""")
    print("table series:")
    rows = c.fetchall()
    for row in rows:
        print(row)
    
    c.execute("""SELECT * FROM works""")
    print("table works:")
    rows = c.fetchall()
    for row in rows:
        print(row)
    
    c.execute("""SELECT * FROM genres""")
    print("table genres:")
    rows = c.fetchall()
    for row in rows:
        print(row)

    c.execute("""SELECT * FROM users""")
    for row in c.fetchall():
        print(row)
    return 

def main(args):
    conn = sqlite3.connect(args.db_file)
    c = conn.cursor()
    create_tables(c)

    book_fts = search.FTS4SpellfixSearch(conn, './spellfix', table_name="fts4_book")
    book_fts.create_schema()

    author_fts = search.FTS4SpellfixSearch(conn, './spellfix', table_name="fts4_author")
    author_fts.create_schema()

    # print_tables(c)
    
    print("-- INSERT DATA --")
    if args.table_name == "user":
        c.execute("""INSERT INTO users (user_first_name, user_last_name) VALUES ("john","doe")""")
        c.execute("""INSERT INTO users (user_first_name, user_last_name) VALUES ("amanda", "white")""")
        c.execute("""INSERT INTO user_book (user_id, book_id, return_date, is_returned) VALUES (?,?,?,?)""", (1, 1, "12/28/2021", 0))
    else:
        file = open(args.file_path)
        csvreader = csv.reader(file, delimiter="\t")
        header = next(csvreader)

        count = 0
        mismatches = 0

        for row in csvreader:
            count+=1
            if len(row) != len(header):
                mismatches+=1
                print("size mismatch!!")
                # print(f"len(row) {len(row)} -- len(header) {len(header)}" )
                # print(header)
                # print(row)
                continue

            if count % 50000 == 0:
                print("currently ", count)

            values = {}
            for i ,col in enumerate(header):
                if row[i]:
                    values[col] = row[i]
                else:
                    values[col] = None

            if args.table_name == "book_info":
                if values["title"]:
                    book_fts.index_row(
                        (values["book_id"], values["title"])
                    )
                    c.execute("""INSERT INTO book_info (isbn, format, 
                                publisher, num_pages, country_code, language_code, 
                                publication_year, book_id, work_id, is_available) 
                                VALUES (?, ?, ?, ?,?, ?, ?, ?, ?, ?)""",
                                (values["isbn"], values["format"], values["publisher"], values["num_pages"], values["country_code"],
                                values["language_code"], values["publication_year"], values["book_id"], values["work_id"], 1))
                else:
                    print("missing title!!")
                    mismatches+=1
                    continue
                
                if values["series"]:
                    for series_id in values["series"].split(" "):
                        c.execute("""INSERT INTO book_series (book_id, series_id) 
                                    VALUES (?, ?)""", (values["book_id"], series_id))

                if values["authors"]:
                    for author_id in values["authors"].split(" "):
                        c.execute("""INSERT INTO book_authors (book_id, author_id) VALUES (?, ?)""", 
                                    (values["book_id"], author_id))

                if values["similar_books"]:
                    for similar_book_id in values["similar_books"].split(" "):
                        c.execute("""INSERT INTO book_similar_books (book_id, similar_book_id) VALUES (?, ?)""", 
                                    (values["book_id"], similar_book_id))

            elif args.table_name == "authors":
                author_fts.index_row((values["author_id"], values["name"]))

            elif args.table_name == "series":
                c.execute("""INSERT INTO series (series_id, series_works_count, primary_work_count, title) VALUES (?,?,?,?)""",
                (values["series_id"], values["series_works_count"], values["primary_work_count"], values["title"]))

            elif args.table_name == "works":
                c.execute("""INSERT INTO works (original_publication_year, work_id, original_title) VALUES (?, ?,?)""",
                (values["original_publication_year"], values["work_id"], values["original_title"]))    

            elif args.table_name == "genres":
                if values["genres"]:
                    for genre in values["genres"].replace(",","").split(" "):
                        c.execute("""INSERT INTO genres (book_id, genre) VALUES (?, ?)""",
                        (values["book_id"], genre))

        file.close()
        print(f"Total {count}. Mismatch {mismatches}. Percentage {mismatches/ count * 100}")

    conn.commit()
    conn.close()

if __name__ == "__main__": 
    parser = argparse.ArgumentParser(description='specify specific db')

    parser.add_argument('--table_name',
                        help='name of database table')

    parser.add_argument('--file_path',
                        help='path to the csv file')

    parser.add_argument('--db_file',
                        help="name of the database", default="book_rent.db")

    args = parser.parse_args()

    main(args)