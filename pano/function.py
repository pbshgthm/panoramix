from copy import deepcopy
from core.arithmetic import simplify_bool
from core.masks import mask_to_type, type_to_mask
from pano.matcher import Any, match
from utils.helpers import (
    EasyCopy,
    find_f_list,
    opcode,
    replace_f,
    padded_hex,
)


def find_parents(exp, child):
    if type(exp) not in (list, tuple):
        return []

    res = []

    for e in exp:
        if e == child:
            res.append(exp)
        res.extend(find_parents(e, child))

    return res


class Function(EasyCopy):
    def __init__(self, hash, trace, nonpayable=None):
        self.hash = hash

        self.mutability = None

        self.trace = deepcopy(trace)
        self.params = self.make_params()
        self.trace = self.cleanup_masks(self.trace)
        self.logs = []
        self.returns = None
        self.nonpayable = nonpayable

        self.analyse()
        self.data = {
            "hash": self.hash,
            "mutability": self.mutability,
            "params": self.params,
            "returns": self.returns,
            "logs": self.logs
        }

    def cleanup_masks(self, trace):
        def rem_masks(exp):
            if m := match(exp, ("bool", ("cd", ":int:idx"))):
                idx = m.idx
                if idx in self.params and self.params[idx][0] == "bool":
                    return ("cd", idx)

            elif m := match(exp, ("mask_shl", ":size", 0, 0, ("cd", ":int:idx"))):
                size, idx = m.size, m.idx
                if idx in self.params:
                    kind = self.params[idx][0]
                    def_size = type_to_mask(kind)
                    if size == def_size:
                        return ("cd", idx)

            return exp

        return replace_f(trace, rem_masks)

    def make_params(self):

        def f(exp):
            if match(exp, ("mask_shl", Any, Any, Any, ("cd", Any))) or match(
                exp, ("cd", Any)
            ):
                return [exp]
            return []

        occurences = find_f_list(self.trace, f)

        sizes = {}
        for o in occurences:
            if m := match(o, ("mask_shl", ":size", Any, Any, ("cd", ":idx"))):
                size, idx = m.size, m.idx

            if m := match(o, ("cd", ":idx")):
                idx = m.idx
                size = 256

            if idx == 0:
                continue

            if m := match(idx, ("add", 4, ("cd", ":in_idx"))):
                # this is a mark of 'cd' being used as a pointer
                sizes[m.in_idx] = -1
                continue

            if idx not in sizes:
                sizes[idx] = size

            elif size < sizes[idx]:
                sizes[idx] == size

        for idx in sizes:
            if type(idx) != int or (idx - 4) % 32 != 0:
                # unusual cd (not aligned)
                return {}

            # for every idx check if it's a bool by any chance
        for idx in sizes:
            li = find_parents(self.trace, ("cd", idx))
            for e in li:
                if opcode(e) not in ("bool", "if", "iszero"):
                    break

                if m := match(e, ("mask_shl", Any, ":off", Any, ":val")):
                    off, val = m.off, m.val
                    assert val == ("cd", idx)
                    if off != 0:
                        sizes[idx] = -2  # it's a tuple!
            else:
                sizes[idx] = 1

        res = {}
        count = 1
        for k in sizes:

            if type(k) != int:
                # unusual calldata reference
                return {}

        for idx in sorted(sizes.keys()):
            size = sizes[idx]

            if size == -2:
                kind = "tuple"
            elif size == -1:
                kind = "array"
            elif size == 1:
                kind = "bool"
            else:
                kind = mask_to_type(size, force=True)

            assert kind != None, size

            res[idx] = (kind, f"_param{count}")
            count += 1

        params = []
        for i in res:
            params.append(res[i][0])
        return params

    def analyse(self):
        assert len(self.trace) > 0

        def find_returns(exp):
            if opcode(exp) == "return":
                return [exp]
            else:
                return []

        self.returns = True if "return" in str(self.trace) else False

        second = self.trace[1]

        if (
            opcode(second) == "if"
            and simplify_bool(second[1]) == "callvalue"
            and (second[2][0] == ("revert", 0) or opcode(second[2][0]) == "invalid")
        ):
            self.trace = self.trace[1][3]
        elif (
            opcode(second) == "if"
            and simplify_bool(second[1]) == ("iszero", "callvalue")
            and (second[3][0] == ("revert", 0) or opcode(second[3][0]) == "invalid")
        ):
            self.trace = self.trace[1][2]
        else:
            self.mutability = "payable"

        view_disqualifiers = [
            "store",
            "selfdestruct",
            "call",
            "delegatecall",
            "codecall",
            "create",
        ]

        if not self.mutability:
            self.mutability = "view"
            for op in view_disqualifiers:
                if f"'{op}'" in str(self.trace):
                    self.mutability = "nonpayable"
                    break

            if self.mutability == "view":
                if not "'storage'" in str(self.trace):
                    self.mutability = "pure"

        self.mutability = "nonpayable" if self.nonpayable else self.mutability

        def l(exp):
            log = []
            if match(
                exp, ("log", Any)) or match(
                    exp, ("log", Any, Any)) or match(
                        exp, ("log", Any, Any, Any)) or match(
                            exp, ("log", Any, Any, Any, Any)) or match(
                                exp, ("log", Any, Any, Any, Any, Any)):

                log = [padded_hex(exp[2], 64)
                       if type(exp[2]) is int else '_UNKNOWN']
            return log

        logs = find_f_list(self.trace, l)
        self.logs = list(set(logs))

        if len(self.logs) > 0:
            self.mutability = "nonpayable"
