import timeout_decorator
from pano.function import Function
from pano.loader import Loader
from pano.vm import VM
import json


def decompile(bytecode):

    loader = Loader(code)
    loader.run(VM(loader, just_fdests=True))

    problems = {}
    functions = {}

    for (hash, target, stack) in loader.func_list:

        try:
            if target > 1 and loader.lines[target][1] == "jumpdest":
                target += 1

            @timeout_decorator.timeout(120, use_signals=True)
            def dec():
                trace = VM(loader).run(target, stack=stack)
                return trace

            trace = dec()
            func = Function(hash, trace, nonpayable=loader.nonpayable)
            if func.hash == "_fallback()":
                if str(func.trace) == "[('setmem', ('range', 64, 32), 96), ('revert', 0)]":
                    continue
            functions[hash] = func

        except Exception as e:
            import sys
            import os
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(exc_type, exc_obj, exc_tb)
            print('PANA', hash, e)

    for i in functions:
        for j in functions[i].data:
            print(j, ":", functions[i].data[j])
        print('\n')
        # print(functions[i].trace)
        print('\n')
        pass


with open('sample.txt', "r") as f:
    code = f.read()
    decompile(code)
