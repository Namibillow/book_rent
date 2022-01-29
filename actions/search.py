"""
    Class support full text search for sqlite. 
    ref: https://stackoverflow.com/questions/52803014/sqlite-with-real-full-text-search-and-spelling-mistakes-ftsspellfix-together
"""

import re
import sqlite3
import sys
import time 

class FTS4SpellfixSearch(object):
    def __init__(self, conn, spellfix1_path, table_name):
        self.conn = conn
        self.conn.enable_load_extension(True)
        self.conn.load_extension(spellfix1_path)
        self.table_name = table_name

    def create_schema(self):
        if self.table_name == "fts4_book":
            self.conn.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS fts4_book
                    USING fts4(
                        title   TEXT    NOT NULL,
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS fts4_book_info_terms
                    USING fts4aux(fts4_book);
                """
            )
        elif self.table_name == "fts4_author":
            self.conn.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS fts4_author
                    USING fts4(
                        author_name   TEXT    NOT NULL,
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS fts4_author_term
                    USING fts4aux(fts4_author);
                """
            )
        
        self.conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS spellfix1data
                    USING spellfix1""")

    def index_row(self, row):
        # print(" -- starting -- ")
        # start = time.time()
        cursor = self.conn.cursor()
        with self.conn:
            if self.table_name == "fts4_book":
                cursor.execute("INSERT INTO fts4_book (rowid, title) VALUES (?, ?)", row)
                cursor.execute(
                    """
                    INSERT INTO spellfix1data(word)
                    SELECT term FROM fts4_book_info_terms
                    WHERE col=0 AND
                        term not in (SELECT word from spellfix1data_vocab)
                    """
                )
            elif self.table_name == "fts4_author":
                cursor.execute("INSERT INTO fts4_author (rowid, author_name) VALUES (?, ?)", row)
                cursor.execute(
                    """
                    INSERT INTO spellfix1data(word)
                    SELECT term FROM fts4_author_term
                    WHERE col=0 AND
                        term not in (SELECT word from spellfix1data_vocab)
                    """
                )
        # end = time.time()
        # print(f"It took: {end - start}")
    # fts3 / 4 search expression tokenizer
    # no attempt is made to validate the expression, only
    # to identify valid search terms and extract them.
    # the fts3/4 tokenizer considers any alphanumeric ASCII character
    # and character in the range U+0080 and over to be terms.
    if sys.maxunicode == 0xFFFF:
        # UCS2 build, keep it simple, match any UTF-16 codepoint 0080 and over
        _fts4_expr_terms = re.compile(u"[a-zA-Z0-9\u0080-\uffff]+")
    else:
        # UCS4
        _fts4_expr_terms = re.compile(u"[a-zA-Z0-9\u0080-\U0010FFFF]+")

    def _terms_from_query(self, search_query):
        """Extract search terms from a fts3/4 query

        Returns a list of terms and a template such that
        template.format(*terms) reconstructs the original query.
        """
        template, terms, lastpos = [], [], 0
        for match in self._fts4_expr_terms.finditer(search_query):
            token, (start, end) = match.group(), match.span()
            # full search term
            terms.append(token)
            token = "{}"
            template += search_query[lastpos:start], token
            lastpos = end
        template.append(search_query[lastpos:])
        return terms, "".join(template)

    def spellcheck_terms(self, search_query):
        cursor = self.conn.cursor()
        base_spellfix = """
            SELECT :term{0} as term, word FROM spellfix1data
            WHERE word MATCH :term{0} and top=1
        """
        terms, template = self._terms_from_query(search_query)
        params = {"term{}".format(i): t for i, t in enumerate(terms, 1)}
        query = " UNION ".join(
            [base_spellfix.format(i + 1) for i in range(len(params))]
        )
        cursor.execute(query, params)
        correction_map = dict(cursor)
        return template.format(*(correction_map.get(t, t.lower()) for t in terms))

    def search_by_rowid(self, rowid):
        cursor = self.conn.cursor()
        if self.table_name=="fts4_book":
            fts_query = "SELECT title FROM fts4_book WHERE rowid = ?"
        elif self.table_name == "fts4_author":
            fts_query = "SELECT author_name FROM fts4_author WHERE rowid = ?"
        cursor.execute(fts_query, (rowid,))
        return cursor.fetchone()

    def search(self, search_query):
        corrected_query = self.spellcheck_terms(search_query)
        cursor = self.conn.cursor()
        fts_query = ""
        if self.table_name=="fts4_book":
            fts_query = "SELECT rowid, * FROM fts4_book WHERE fts4_book MATCH ?"
        elif self.table_name == "fts4_author":
            fts_query = "SELECT rowid, * FROM fts4_author WHERE fts4_author MATCH ?"
        cursor.execute(fts_query, (corrected_query,))
        return {
            "terms": search_query,
            "corrected": corrected_query,
            "results": cursor.fetchall(),
        }

if __name__ == "__main__":
    from pprint import pprint
    db = sqlite3.connect("testing.db")
 
    # fts = FTS4SpellfixSearch(db, './spellfix', table_name="fts4_book")
    # fts.create_schema()
    # fts.index_row(
    #     (1,"Deviled Egg Murder: Book 6 in The Bandit Hills Series"),
    #     # (1,"Growltiger's Last Stand and Other Poems"),  
    #     (2,"Live Bait (Monkeewrench #2)"),  
    #     (None,"The Cocktail Party"),   
    #     (4,"El secuestro de Robles Martínez"),  
    #     (5,"Mother To The World"),  
    #     (6,"Skynappers"),   
    # )

    # pprint(fts.search('Live Bite'))  # edgecase, multiple spellfix matches
    # pprint(fts.search('Love Bite'))
    # pprint(fts.search('Mutter to the world'))
    # pprint(fts.search('cocktail party'))
    # print()

    fts2 = FTS4SpellfixSearch(db, './spellfix', table_name="fts4_author")
    fts2.create_schema()
    # fts2.index_row(
    #     # (1,"J.K. Rowling"),
    #     # (2,"Stephen King"),  
    #     # (None,"Danzy Senna"),   
    #     # (4,"George R.R Martin"),  
    #     (5,"Khaled Hosseini")
    # )
    pprint(fts2.search([])["results"])
    # pprint(fts2.search('JK Rowling'))
    # pprint(fts2.search('Stephanie King'))
    # pprint(fts2.search('Danzy Senna'))
    # pprint(fts2.search('Daizy Senna')) # doesn't work
    # pprint(fts2.search('George Martin'))

    # c = db.cursor()
    # c.execute("""SELECT rowid, * FROM fts4data""")
    # print(c.fetchall())