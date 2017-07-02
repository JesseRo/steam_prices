from endpoint import *


def setup_routes(app):
    app.router.add_get('/', index)
    app.router.add_post('/prices', prices)
    app.router.add_post('/storage', storage_)
    app.router.add_get('/query', query)
    app.router.add_post('/login', login)
    app.router.add_get('/islogin', islogin)
