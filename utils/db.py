import pymysql
import queue
from config import DB_CONFIG

_idle = queue.Queue(maxsize=20)


def _new_conn():
    return pymysql.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        charset=DB_CONFIG['charset'],
        cursorclass=pymysql.cursors.DictCursor
    )


class _PooledConn:
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        try:
            self._conn.rollback()
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass
            return
        try:
            _idle.put_nowait(self._conn)
        except queue.Full:
            try:
                self._conn.close()
            except Exception:
                pass


def get_db():
    try:
        conn = _idle.get_nowait()
    except queue.Empty:
        conn = _new_conn()
    try:
        conn.ping(reconnect=True)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        conn = _new_conn()
    return _PooledConn(conn)
