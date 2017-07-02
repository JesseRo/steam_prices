import uuid

from aiohttp import web
import aiohttp_jinja2
import aiohttp
import sqlalchemy as sa
import functools
import json
from datetime import datetime, date
import numpy as np
from aiohttp_session import setup, get_session, session_middleware
import asyncio
from tables import *


def json_dumps(data, **kwargs):
    return json.dumps(data, cls=CJsonEncoder, **kwargs)


class CJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        else:
            return json.JSONEncoder.default(self, obj)


@aiohttp_jinja2.template('index.html')
async def index(request):
    session = await get_session(request)
    session['111'] = 111
    return {
        'display': 'None',
        'items': None,
    }


def check_auth(session):
    if 'user_id' in session:
        return True
    else:
        return False

async def login(request):
    data = await request.post()
    if 'username' not in data or 'password' not in data:
        return web.json_response({
            'result': False,
            'message': '用户名或密码未填写完整'
        })
    username = data['username']
    password = data['password']
    db = request.app['db']
    async with db.acquire() as conn:
        _query = sa.select([reg_user.c.expire]).where(
            sa.and_(reg_user.c.username == username, reg_user.c.password == password)
        )
        user = [dict(row.items()) async for row in conn.execute(_query)]
        if len(user) > 0 and user[0]['expire'] > datetime.now():
            session = await get_session(request)
            session['user_id'] = str(uuid.uuid4())
            return web.json_response({
                'result': True
            })
        else:
            return web.json_response({
                'result': False,
                'message': '未购买会员或会员已过期'
            })

async def islogin(request):
    session = await get_session(request)
    return web.json_response({
        'result': check_auth(session)
    })


@aiohttp_jinja2.template('index.html')
async def prices(request):
    session = await get_session(request)
    data = await request.post()

    if 'market' not in data:
        return web.json_response({
            'result': False,
            'code': 'no_market',
            'message': '未指定市场..'
        })
    market = data['market']

    if 'price_type' not in data:
        price_type = 'sell'
    else:
        price_type = data['price_type']

    if market == 'c5' and price_type == 'buy':
        if not check_auth(session):
            return web.json_response({
                'result': False,
                'code': 'auth_err',
                'message': '不是注册用户..'
            })

    if 'page' not in data:
        page = 1
    else:
        page = data['page']
        if page == '' or int(page) <= 0:
            page = 1
        else:
            page = int(page)

    db = request.app['db']

    view = session['view'] if 'view' in session else None
    p_t = session['price_type'] if 'price_type' in session else None
    mk = session['market'] if 'market' in session else None
    if view is None or (p_t is None or p_t != price_type) or (mk is None or mk != market):
        storage = session['storage'] if 'storage' in session else None
        description = session['description'] if 'description' in session else None

        if storage is None or description is None:
            return {
                'result': False,
                'reason': 'loading'
            }

        hash_names = tuple(map(lambda _ds: _ds['market_hash_name'], description.values()))

        if market == 'steam':
            async with db.acquire() as conn:
                _query = sa.select([goods.c.name, goods.c.price]).where(sa.and_(
                    goods.c.name.in_(hash_names), goods.c.price is not None, goods.c.price != 'error'))
                data = [dict(row.items()) async for row in conn.execute(_query)]
                # data.sort(key=lambda d: float(d['price']), reverse=True)
                data = dict({d['name']: d for d in data})

                items = []
                for name in description:
                    ds = description[name]
                    d = data.get(name, None)
                    item = storage[ds['id']]
                    for it in item:
                        it['price'] = np.float(d['price']) if d is not None else np.inf
                        it['imgurl'] = ds['icon_url']
                        it['name_color'] = ds['name_color']
                        it['descriptions'] = ds['descriptions']
                    items += item
        else:
            async with db.acquire() as conn:
                if price_type == 'buy':
                    price = c5items.c.c5qiugouprice.label('price')
                    _query = sa.select([c5items.c.markethashname, price]).where(sa.and_(
                        c5items.c.markethashname.in_(hash_names), price is not None, price != 'error'))
                elif price_type == 'sell':
                    price = c5items.c.c5sellprice.label('price')
                    _query = sa.select([c5items.c.markethashname, price]).where(sa.and_(
                        c5items.c.markethashname.in_(hash_names), price is not None, price != 'error'))
                data = [dict(row.items()) async for row in conn.execute(_query)]
                # data.sort(key=lambda d: float(d['price']), reverse=True)
                data = dict({d['markethashname']: d for d in data})

                items = []
                for name in description:
                    ds = description[name]
                    d = data.get(name, None)
                    item = storage[ds['id']]
                    for it in item:
                        it['price'] = np.float(d['price']) if d is not None else np.inf
                        it['imgurl'] = ds['icon_url']
                        it['name_color'] = ds['name_color']
                        it['descriptions'] = ds['descriptions']
                    items += item

        items.sort(key=lambda _it: _it['price'], reverse=True)
        _prices = np.array(list(map(lambda a: a['price'], items)))
        _prices[np.isinf(_prices)] = np.nan
        total = np.nansum(_prices)

        session['price_type'] = price_type
        session['market'] = market
        session['view'] = view = {
            'display': 'block',
            'items': items,
            'total': total,
            'taxed_total': '%.2f' % (total * .8),
            'rmb_total': '%.2f' % (total * .8 * 6),
            'page': int(np.ceil(len(items) / 100))
        }
    _view = view.copy()
    _view['current_page'] = page
    _view['market'] = market
    _view['price_type'] = price_type
    _items = _view['items']
    _view['items'] = _items[100 * (page - 1): 100 * page]
    return _view

async def storage_(request):
    user_session = await get_session(request)

    data = await request.post()
    if 'steamid' in data:
        steamid = data['steamid']
    elif 'gf_id' in data:
        steamid = str(int(data['gf_id']) + 76561197960265728)
    else:
        return web.json_response({
            'result': False,
            'code': 10001,
            'message': 'steam id 错误..'
        })

    if 'gameid' not in data:
        return web.json_response({
            'result': False,
            'code': 10002,
            'message': '未指定游戏..'
        })
    game = data['gameid']
    #
    # game = '570'
    #
    # steamid = str(76561198069046842)
    more_start = 0
    storage_url = 'https://steamcommunity.com/profiles/%s/inventory/json/%s/2?trading=1&start=' % (steamid, game)
    session = aiohttp.ClientSession()
    try:
        resp = await session.get(storage_url + str(more_start))
        res = await resp.json()
        while res is None:
            await asyncio.sleep(10)
        if res['success']:
            storage = {}
            description = list()

            def parse(_res, _storage):
                def group_by(group, item):
                    key = item['classid'] + '_' + item['instanceid']
                    if key not in group:
                        group[key] = list()
                    group[key].append(item)
                    return group

                _items = _res['rgInventory'].values()
                _items = functools.reduce(group_by, list(_items), _storage)
                for k, v in _res['rgDescriptions'].items():
                    v['id'] = k
                return _items, description + list(_res['rgDescriptions'].values())

            storage, description = parse(res, storage)
            while res['more']:
                more_start = int(res['more_start'])
                resp = await session.get(storage_url + str(more_start))
                res = await resp.json()
                while res is None:
                    await asyncio.sleep(10)
                storage, description = parse(res, storage)

            description = dict({ds['market_hash_name']: ds for ds in description})
            user_session['storage'] = storage
            user_session['description'] = description
            # user_session.pop('storage_err', None)
    except Exception as e:
        user_session['storage_err'] = True
        return web.json_response({
            'result': False,
            'reason': 'storage_err'
        })
    finally:
        await session.close()
        return web.json_response({
            'result': True
        })

async def query(request):
    session = await get_session(request)
    if 'storage_err' in session:
        return web.json_response({
            'result': False,
            'reason': 'storage_err'
        })
    if 'storage' in session and 'description' in session:
        return web.json_response({
            'result': True
        })
    else:
        return web.json_response({
            'result': False,
            'reason': 'loading'
        })
