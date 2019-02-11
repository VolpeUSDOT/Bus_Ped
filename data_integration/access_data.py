from datetime import datetime
import numpy as np
import pandas as pd
import sqlite3
import os.path


# Create connection to integrated data
def create_connection(db_path):
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except Error as e:
        print(e)

    return None


def summarize_tables(conn):
    """
    Query number of rows, columns, and column names in each table
    :param conn: Connection object
    :return:
    """

    cur = conn.cursor()
    #cur.execute("SELECT COUNT(*) FROM hotspot_data_product")
    cur.execute("SELECT COUNT(*) FROM longitudinal_data_product")

    rows = cur.fetchall()

    print(rows)


def main():

    db_path = os.path.join(r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data\Data Integration',
                            'ituran_synchromatics_data.sqlite')
    conn = create_connection(db_path)
    with conn:
        print(db_path)
        print("Summarizing tables")
        summarize_tables(conn)


if __name__ == '__main__':
    main()
