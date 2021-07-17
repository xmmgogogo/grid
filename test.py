class ParentA:
    def __init__(self):
        print("ParentA init-1")

    def run(self):
        print("ParentA run")


class ClassA:
    def __init__(self):
        print("init")
        pass

    def run(self):
        print("run")
        pass


a = ClassA()
print(a)