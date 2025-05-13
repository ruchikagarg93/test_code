import logging
from typing import Any, Optional

from sqlalchemy import MetaData, Table, and_, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
class Singleton(type):
    """Singleton Metaclass."""

    _instances = {}

    def __call__(cls, *args, **kwargs):  # noqa: D102
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

class DBController(metaclass=Singleton):
    """Class to handle database connection, session and operations.

    Args:
        conn_str: A connection string to connect to postgres database
    """

    def __init__(
        self,
        conn_str: Optional[str],
    ) -> None:
        """Sets up database client."""
        self.conn_str = conn_str
        self.engine = create_engine(conn_str, pool_pre_ping=True)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)
        self.db = self.engine

    def get_session(self) -> Session:
        """Create and return a new database session.

        Returns:
            Session: A new SQLAlchemy session instance.
        """
        Session = sessionmaker(bind=self.db)
        session = Session()
        return session

    def get_table(self, table_name: str) -> Table:
        """Gets a table from metadata.

        Args:
            table_name: The name of the table to get from the metadata.

        Raises:
            KeyError: If the table is not found in the metadata
        """
        try:
            return self.metadata.tables[table_name]
        except KeyError as err:
            logging.error(f"table {table_name} not found in Database")
            raise KeyError(f"Table {table_name} not found in metadata.") from err

    def execute(self, query_stmt) -> list[dict[str, Any]]:
        """Executes query statement.

        Executes the query statement and returns the list of all rows returned by the query.

        Args:
            query_stmt: The query to execute.
        """
        session = self.get_session()
        with session.begin():
            result = session.execute(query_stmt)
            rows = result.fetchall()
            result_dicts = [dict(zip(result.keys(), row)) for row in rows]
            return result_dicts

class RequestStatus:
    """Class to get the monitoring request data from the database."""

    def __init__(self,host,port,username,password,databasename):
        # self.db = DBController(conn_str="postgresql+psycopg2://amlmonitoradmin:e74ad4e1X1180X4626X9dbfX8eff973f47f6@bcue2prodamlfx.postgres.database.azure.com:5432/cismlopscoreus")
        self.db = DBController(conn_str=f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{databasename}")


    def get_reqids(self, application, consumer,  start_time, end_time , country=None, characteristics=None,) -> dict:
        """Gets request in a time range if provide in input JSON if not get request ids for last 90 days."""
        result = {}

        result["requestId"] = []

        cis_request = self.db.get_table("cis_request")
        cis_request_umbrella = self.db.get_table("cis_request_umbrella")
        cis_request_status = self.db.get_table("cis_request_status")
        cis_request_json = self.db.get_table("cis_request_json")
        stmt = select(cis_request.c.request_id).select_from(
            cis_request.join(
                cis_request_umbrella,
                cis_request.c.request_id == cis_request_umbrella.c.request_id,
            )
        )

        conditions = [
            cis_request_umbrella.c.application == application,
            cis_request_umbrella.c.consumer == consumer,
            cis_request.c.create_datetime_utc.between(start_time, end_time)
        ]
        if characteristics:
            conditions.append(cis_request_umbrella.c.characteristics == characteristics)
        if country:
            conditions.append(cis_request_umbrella.c.country == country.upper())

      
        
        stmt = stmt.where(and_(*conditions))
        print("Executing Query:", stmt.compile(compile_kwargs={"literal_binds": True}))
        res = self.db.execute(stmt)


        
        for items in res:
            result["requestId"].append(items.get("request_id"))


        stmt2 = (
            select(cis_request_json.c.request_id,cis_request_json.c.json)
            .select_from(
                cis_request_status.join(
                    cis_request_json,
                    cis_request_status.c.request_id == cis_request_json.c.request_id,
                )
            )
            .where(and_(
            cis_request_status.c.request_id.in_(result["requestId"])
        ) )
        )

        # stmt = stmt2.where(and_(*conditions))


        res2 = self.db.execute(stmt2)

        total_request = []
        for items in res2:
            try:
                total_request.append([items['request_id'],items['json']['input']['assets'][0]['path'], items['json']['client']])
            except Exception as e:
                continue

        return total_request



from datetime import datetime

if __name__=="__main__":
    # requestStatus = RequestStatus()
    requestStatus = RequestStatus("bcewprodamlfx.postgres.database.azure.com","5432","amlmonitoradmin","bf2b5d08Xdfd3X4bacX8556Xd6cb22c2ec5e","cismlopscoreeu")
    
    data=  requestStatus.get_reqids(application="projectrun", consumer="22c-copy-item",country="GB",characteristics=["prediction"], start_time= datetime.strptime("2024-10-28", "%Y-%m-%d"),end_time= datetime.now())
    print(data)
    
