
class A(object):
    def __init__(self):
        self.b = 1

    def __get__(self, instance, owner):
        print(1)

    def __getattr__(self, item):
        a.__setattr__(item, 5)
        return item


a = A()
print(a.c)
print(a.c)