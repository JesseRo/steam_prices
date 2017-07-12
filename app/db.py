import aiomysql.sa
import sqlalchemy as sa


class Tables:
    def __init__(self, engine, meta):
        self.engine = engine
        self.meta = meta

    def __getattr__(self, item):
        field = sa.Table(item, self.meta, autoload=True, autoload_with=self.engine)
        self.__setattr__(item, field)
        return field

async def init_mysql(app):
    conf = app['config']
    engine = await aiomysql.sa.create_engine(
        db=conf['database'],
        host=conf['host'],
        port=conf['port'],
        user=conf['user'],
        password=conf['password'],
        minsize=conf['minsize'],
        maxsize=conf['maxsize'],
        charset='utf8',
        autocommit=True
    )
    #  seemed like aiomysql do not support schema creation for now..
    # engine = create_engine('mysql+pymysql://jesse:123456@119.28.64.212:3306/aio-market')
    app['db'] = engine
    # meta.create_all(engine)

    meta = sa.MetaData()
    app['tables'] = Tables(engine, meta)

async def close_mysql(app):
    app['db'].close()
    await app['db'].wait_closed()


