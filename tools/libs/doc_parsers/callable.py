import inspect, os

class Parser(object):
    def __init__(self, root_path: str, callable_obj) -> None:
        self._callable = callable_obj
        self._doc = callable_obj.__doc__
        self._root_path = root_path
        self._doc_info: dict = {}
        self._raw_doc: dict = {
            'signature': [],
            'description': [],
            'args': [],
            'returns': [],
            'raises': [],
            'examples': [],
        }
    
    def __call__(self) -> dict:
        self.handle()
        return self._doc_info
    
    def handle(self):
        _docs = []
        _doc = ''
        _type = None
        for idx, doc_line in enumerate(self._doc.split('\n')):
            if idx == 0:
                _type = 'description'
            else:
                _doc_line = doc_line.strip()
                if not _doc_line:
                    continue
                if _doc_line.lower().replace(':', '') in self._raw_doc:
                    _type = _doc_line.strip().lower().replace(':', '')
                    continue

            self._raw_doc[_type].append(doc_line)

        doc_info = {}
        for _type, _raw_docs in self._raw_doc.items():
            _type = _type.lower()
            handle_fn = f'handle_{_type}'
            if hasattr(self, handle_fn):
                doc_info[_type] = getattr(self, handle_fn)(_raw_docs)
            else:
                doc_info[_type] = self.handle_default(_raw_docs)
        self._doc_info = doc_info

    def handle_args(self, _raw_docs) -> str:
        try:
            sig = inspect.signature(self._callable)
            args = []
            if _raw_docs:
                for _doc in _raw_docs:
                    if _doc.strip().title() == 'None':
                        continue
                    _name, _desc = _doc.strip().split(':', 1)
                    arg = { 'name': _name, 'desc': _desc, }
                    _name = _name.strip('*')
                    arg.update({
                        'type': str(sig.parameters[_name].annotation),
                        'deault': sig.parameters[_name].default
                    })
                    args.append(arg)
            return args
        except BaseException as exc:
            raise
        return []

    def handle_default(self, _raw_docs) -> str:
        return '\n'.join(_raw_docs)
