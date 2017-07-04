import pathlib
from aiohttp import web
from binstar_client.utils import load_config
from app.router import setup_routes
from app.db import *
import aiohttp_jinja2
import jinja2
import aiohttp_session
import base64
from cryptography import fernet
from aiohttp_session.redis_storage import RedisStorage
import aioredis
import asyncio

app = web.Application()
conf = load_config(str(pathlib.Path('config/aio-market.yaml')))
app['config'] = conf
app.on_startup.append(init_mysql)
app.on_cleanup.append(close_mysql)
app.router.add_static('/static', path=str('static'), name='static')
aiohttp_jinja2.setup(app, loader=jinja2.PackageLoader('app', 'templates'))

fernet_key = fernet.Fernet.generate_key()
secret_key = base64.urlsafe_b64decode(fernet_key)
redis = asyncio.get_event_loop().run_until_complete(aioredis.create_pool(('localhost', 6379)))
aiohttp_session.setup(app, RedisStorage(redis, max_age=7 * 24 * 60 * 60))
setup_routes(app)
web.run_app(app, host='172.17.83.33', port=80)
