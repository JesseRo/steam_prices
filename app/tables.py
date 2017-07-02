import sqlalchemy as sa

meta = sa.MetaData()

goods = sa.Table(
    'goods', meta,
    sa.Column('name', sa.String(50), nullable=False),
    sa.Column('price', sa.String(10), nullable=True),
    sa.Column('imgurl', sa.String(200), nullable=True),
    sa.Column('name_color', sa.String(10), nullable=True)
)

c5items = sa.Table(
    'c5items', meta,
    sa.Column('markethashname', sa.String(50), nullable=False),
    sa.Column('c5sellprice', sa.String(10), nullable=True),
    sa.Column('c5qiugouprice', sa.String(10), nullable=True),
)

reg_user = sa.Table(
    'auth', meta,
    sa.Column('username', sa.String(50), nullable=False),
    sa.Column('password', sa.String(50), nullable=False),
    sa.Column('expire', sa.DATETIME(), nullable=False),
)
