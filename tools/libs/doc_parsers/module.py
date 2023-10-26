import inspect, os

class Parser(object):
    def __init__(self, root_path: str, package) -> None:
        self._package = package
        self._doc = package.__doc__
        self._root_path = root_path
        self._doc_info: dict = {}
        self._raw_doc: dict = {
            'module': [],
            'title': [],
            'description': [],
            'author': [],
            'examples': [],
            'exposes': [],
        }
    
    def __call__(self) -> dict:
        self.handle()
        return self._doc_info
    
    def handle(self):
        _docs = []
        _doc = ''
        _type = None
        for doc_line in self._doc.split('\n'):
            if not doc_line.strip():
                continue
            elif ':' in doc_line:
                _type, _doc = doc_line.split(':', 1)
                if _doc.strip():
                    _docs.append(_doc.strip())
            else:
                _docs.append(doc_line)
            
            if _type is not None:
                if _type in self._raw_doc:
                    self._raw_doc[_type].extend(_docs)
                    _docs = []
        
        doc_info = {}
        for _type, _raw_docs in self._raw_doc.items():
            handle_fn = f'handle_{_type}'
            if hasattr(self, handle_fn):
                doc_info[_type] = getattr(self, handle_fn)(_raw_docs)
            else:
                doc_info[_type] = self.handle_default(_raw_docs)
        self._doc_info = doc_info
    
    def handle_module(self, _raw_docs) -> str:
        return _raw_docs[0]

    def handle_title(self, _raw_docs) -> str:
        return _raw_docs[0]

    def handle_description(self, _raw_docs) -> str:
        return _raw_docs[0]
    
    def handle_exposes(self, _raw_docs):
        package_attrs = [attr.replace('-', '').strip() for attr in _raw_docs]
        attr_docs = []
        for attr in package_attrs:
            obj = getattr(self._package, attr)
            attr_doc = {
                'type': 'class',
                'doc': obj.__doc__,
            }
            if inspect.isclass(obj):
                obj_attrs = {
                    f'{attr}.{obj_attr}' : getattr(obj, obj_attr)
                    for obj_attr in obj.__dict__
                    if (
                            obj_attr in ('__init__', '__call__') or not obj_attr.startswith('_')
                        ) and
                        inspect.isfunction(getattr(obj, obj_attr)) and
                        getattr(obj, obj_attr).__doc__
                }
                
                attr_doc['exposes'] = obj_attrs 
            #endif
            attr_docs.append(attr_doc)
        #endfor
        return attr_docs

    def handle_default(self, _raw_docs) -> str:
        return '\n'.join(_raw_docs)
