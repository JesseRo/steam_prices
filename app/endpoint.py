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
from .tables import *
import traceback
import re


def json_dumps(data, **kwargs):
    return json.dumps(data, cls=CJsonEncoder, **kwargs)


def get_tax_price(price):
    if not np.isfinite(price):
        return np.inf
    saleprice = price
    dota2fee = np.floor(saleprice * 1000 * 2 / 23 / 10)
    if dota2fee <= 1:
        dota2fee = 0.01
    else:
        dota2fee = dota2fee / 100
    vfee = np.floor(saleprice * 1000 / 23 / 10)
    if vfee <= 1:
        vfee = 0.01
    else:
        vfee = vfee / 100
    saleprice = saleprice - vfee - dota2fee
    return np.round(saleprice * 100) / 100


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
        'game': '570',
        'market': 'steam',
        'rid': str(uuid.uuid4())
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
    _session = await get_session(request)
    data = await request.post()

    if 'rid' not in data:
        return web.HTTPInternalServerError()

    rid = data['rid']
    if rid not in _session:
        return web.HTTPInternalServerError(text='查询到的库存已过期，请重新查询..')

    session = _session[rid]

    if 'market' not in data:
        market = 'steam'
    else:
        market = data['market']

    if 'game' not in session:
        game = '570'
    else:
        game = session['game']

    if game != '570':
        market = 'steam'

    if 'price_type' not in data:
        price_type = 'sell'
    else:
        price_type = data['price_type']

    if market == 'c5':
        if not check_auth(_session):
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
        no_items = []

        async with db.acquire() as conn:
            transaction = await conn.begin()
            try:
                if market == 'steam':
                    _query = sa.select([goods.c.name, goods.c.price]).where(
                        goods.c.name.in_(hash_names))
                    data = [dict(row.items()) async for row in conn.execute(_query)]
                    # data.sort(key=lambda d: float(d['price']), reverse=True)
                    data = dict({d['name']: d for d in data})

                    items = []
                    for name in description:
                        ds = description[name]
                        d = data.get(name, None)
                        if d is None:
                            no_items.append(ds)
                        ids = set(ds['id'])
                        for _id in ids:
                            item = storage[_id]
                            for it in item:
                                it['price'] = np.float(d['price']) if d is not None else np.inf
                                it['tax_price'] = get_tax_price(it['price'])
                                it['imgurl'] = ds['icon_url']
                                it['name_color'] = ds['name_color']
                                it['descriptions'] = ds.get('descriptions', [])
                                it['market_name'] = ds['market_name']
                                it['type'] = ds['type']
                            items += item
                else:
                    if price_type == 'buy':
                        price = c5items.c.c5qiugouprice.label('price')
                        _query = sa.select([c5items.c.markethashname, price]).where(
                            c5items.c.markethashname.in_(hash_names))
                    elif price_type == 'sell':
                        price = c5items.c.c5sellprice.label('price')
                        _query = sa.select([c5items.c.markethashname, price]).where(
                            c5items.c.markethashname.in_(hash_names))
                    data = [dict(row.items()) async for row in conn.execute(_query)]
                    # data.sort(key=lambda d: float(d['price']), reverse=True)
                    data = dict({d['markethashname']: d for d in data})

                    items = []
                    for name in description:
                        ds = description[name]
                        d = data.get(name, None)
                        if d is None:
                            no_items.append(ds)
                        ids = set(ds['id'])
                        for _id in ids:
                            item = storage[_id]
                            for it in item:
                                if d is not None and d['price'] is not None and d['price'] != 'error':
                                    it['price'] = np.float(d['price'])
                                else:
                                    it['price'] = np.inf
                                it['tax_price'] = get_tax_price(it['price'])
                                it['imgurl'] = ds['icon_url']
                                it['name_color'] = ds['name_color']
                                it['descriptions'] = ds.get('descriptions', [])
                                it['market_name'] = ds['market_name']
                                it['type'] = ds['type']
                            items += item

                if no_items:
                    _query = sa.select([no_item.c.market_hash_name, no_item.c.market])
                    prev_no_items = [row.market_hash_name + '_' + row.market async for row in conn.execute(_query)]
                    # prev_no_items = set(row.market_hash_name + '_' + row.market async for row in conn.execute(_query))
                    _no_items = []
                    for ni in no_items:
                        if not ((ni['market_hash_name'] + '_' + market) in prev_no_items):
                            _no_items.append({
                                'market_hash_name': ni['market_hash_name'],
                                'market_name': ni['market_name'],
                                'market': market
                            })
                    if _no_items:
                        _insert = sa.insert(no_item, _no_items)
                        await conn.execute(_insert)
            except Exception as e:
                traceback.print_exc()
                await transaction.rollback()
            else:
                await transaction.commit()

        items.sort(key=lambda _it: _it['price'], reverse=True)
        _prices = np.array(list(map(lambda a: a['price'], items)))
        _prices[np.isinf(_prices)] = np.nan
        total = np.nansum(_prices)
        range1_num = np.nansum((_prices > 0) & (_prices <= 0.2))
        range1_sum = np.nansum(_prices[(_prices > 0) & (_prices <= 0.2)])
        range2_num = np.nansum((_prices > 0.2) & (_prices <= 1))
        range2_sum = np.nansum(_prices[(_prices > 0.2) & (_prices <= 1)])
        range3_num = np.nansum((_prices > 1) & (_prices <= 10))
        range3_sum = np.nansum(_prices[(_prices > 1) & (_prices <= 10)])
        range4_num = np.nansum((_prices > 10))
        range4_sum = np.nansum(_prices[(_prices > 10)])

        _taxed_prices = np.array(list(map(lambda a: a['tax_price'], items)))
        _taxed_prices[np.isinf(_taxed_prices)] = np.nan
        _taxed_total = np.nansum(_taxed_prices)

        session['price_type'] = price_type
        session['market'] = market
        session['view'] = view = {
            'display': 'block',
            'items': items,
            'number': len(items),
            'total': '%.2f' % total,
            'taxed_total': '%.2f' % _taxed_total,
            'rmb_total': '%.2f' % (total * .8 * 6),
            'page': int(np.ceil(len(items) / 100)),
            'range1_num': int(range1_num),
            'range1_sum': '%.2f' % float(range1_sum),
            'range2_num': int(range2_num),
            'range2_sum': '%.2f' % float(range2_sum),
            'range3_num': int(range3_num),
            'range3_sum': '%.2f' % float(range3_sum),
            'range4_num': int(range4_num),
            'range4_sum': '%.2f' % float(range4_sum),
            'rid': rid
        }
    _view = view.copy()
    _view['current_page'] = page
    _view['market'] = market
    _view['price_type'] = price_type
    _items = _view['items']
    _view['game'] = game
    _view['items'] = _items[100 * (page - 1): 100 * page]
    return _view

async def storage_(request):
    user_session = await get_session(request)
    session = aiohttp.ClientSession()

    data = await request.post()
    if 'steamid' in data:
        steamid = data['steamid']
        if steamid:
            profile_url = re.findall(r'(steamcommunity.*?id/.*?/)', steamid)
            if profile_url:
                profile_resp = await session.get('http://' + profile_url[0])
                profile_resp = await profile_resp.text()
                steamid = re.findall(r'g_rgProfileData = .*?(\d{15,})', profile_resp)
                if steamid:
                    steamid = steamid[0]
    elif 'gf_id' in data:
        steamid = data['gf_id']
        if steamid:
            profile_url = re.findall(r'(steamcommunity.*?id/.*?/)', steamid)
            if profile_url:
                profile_resp = await session.get('http://' + profile_url[0])
                profile_resp = await profile_resp.text()
                steamid = re.findall(r'g_rgProfileData = .*?(\d{15,})', profile_resp)
                if steamid:
                    steamid = steamid[0]
            else:
                steamid = str(int(steamid) + 76561197960265728)

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
    if 'rid' not in data:
        return web.HTTPInternalServerError(text='查询到的库存已过期，请重新查询..')
    rid = data['rid']

    more_start = 0
    storage_url = 'http://steamcommunity.com/inventory/%s/%s/2?l=schinese&count=5000&tradable=1&maketable=1' % (steamid, game)
    # storage_url = 'http://steamcommunity.com/profiles/%s/inventory/json/%s/2?l=schinese&trading=1&start=' % (steamid, game)
    try:
        resp = await session.get(storage_url)
        res = await resp.json()
        while res is None:
            await asyncio.sleep(10)
        if res['success'] == 1:
            storage = {}
            description = list()

            def parse(_res, _storage):
                def group_by(group, item):
                    key = item['classid'] + '_' + item['instanceid']
                    if key not in group:
                        group[key] = list()
                    group[key].append(item)
                    return group

                _items = _res['assets']
                _items = functools.reduce(group_by, list(_items), _storage)
                for v in _res['descriptions']:
                    v['id'] = v['classid'] + '_' + v['instanceid']
                return _items, list(_res['descriptions'])

            storage, description = parse(res, storage)
            while 'more_items' in res and res['more_items'] == 1:
                last_asset = res['last_assetid']
                resp = await session.get(storage_url + '&start_assetid=' + last_asset)
                res = await resp.json()
                while res is None:
                    await asyncio.sleep(10)
                storage, _description = parse(res, storage)
                description += _description
            description = list(filter(lambda ds: ds['marketable'] == 1 and ds['tradable'] == 1, description))

            def redu(des, lis):
                if lis['market_hash_name'] not in des:
                    des[lis['market_hash_name']] = lis
                    des[lis['market_hash_name']]['id'] = [lis['id']]
                else:
                    org = des[lis['market_hash_name']]
                    org['id'].append(lis['id'])
                return des
            description = functools.reduce(redu, description, {})

            r_session = user_session[rid] = {}
            r_session['storage'] = storage
            r_session['game'] = game
            r_session['description'] = description
            r_session.pop('price_type', None)
            r_session.pop('market', None)
            r_session.pop('view', None)
            # user_session.pop('storage_err', None)
        else:
            return web.json_response({
                'result': False,
                'message': '未公开库存资料或者库存为空..'
            })
    except Exception as e:
        await session.close()
        if rid not in user_session:
            user_session[rid] = {}
        user_session[rid]['storage_err'] = True
        return web.json_response({
            'result': False,
            'message': 'storage_err'
        })
    else:
        await session.close()
        return web.json_response({
            'result': True,
            'game': game
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
