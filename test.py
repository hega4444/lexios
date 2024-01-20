import inspect

def mark_method(func):
    setattr(func, 'marked', True)
    return func

class MyClass:
    @mark_method
    def marked_method(self):
        pass

    def unmarked_method(self):
        pass

def get_marked_methods(instance):
    return [method for method, _ in inspect.getmembers(instance, predicate=inspect.ismethod) if hasattr(method, 'marked')]

# Create an instance of MyClass
my_instance = MyClass()

# Get marked methods
marked_methods = get_marked_methods(my_instance)
print("Marked Methods:", marked_methods)
