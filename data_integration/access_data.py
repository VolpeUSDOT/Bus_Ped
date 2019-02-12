import sqlite3
import os.path
import pandas as pd


# Create connection to integrated data
def create_connection(db_path):
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except sqlite3.Error as e:
        print(e)
    return None


def summarize_tables(conn, table):
    """
    Query number of rows, columns, and column names in each table
    :param conn: Connection object
    :return:
    """

    cur = conn.cursor()
    # rows = cur.execute("SELECT COUNT(*) FROM " + table).fetchall()
    df = pd.read_sql_query("SELECT * FROM " + table, conn)

    # cols = list(map(lambda x: x[0], cur.description))

    summary = df.describe(percentiles=[])

    print(table + '\n')
    print("Dimensions:" + str(df.shape))
    print(summary)
    cur.close()

def main():
    db_path = os.path.join(r'\\vntscex.local\DFS\3BC-Share$_Mobileye_Data\Data\Data Integration',
                           'ituran_synchromatics_data.sqlite')
    conn = create_connection(db_path)
    with conn:
        print(db_path)
        print("Summarizing tables")
        summarize_tables(conn, 'longitudinal_data_product')
        summarize_tables(conn, 'hotspot_data_product')


if __name__ == '__main__':
    main()
