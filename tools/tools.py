import argparse, os, sys, typing

class Tools(object):
    def __init__(self):
        self.package_root = os.path.dirname(os.path.dirname(__file__))
        sys.path.append(self.package_root)
    
    def cmd_help(self, **kwargs):
        if 'reason' in kwargs:
            print(kwargs['reason'])
        print('...')
    
    def cmd_doc(self, **kwargs):
        import yaa
        package_names = [
            attr for attr in yaa.__dir__()
            if not attr.startswith('_')
        ]
        docs = self.get_docs(package_names)
        
    def get_docs(self, package_names):
        import yaa
        import inspect
        docs = {}
        for package_name in package_names:
            package = getattr(yaa, package_name)
            if package.__doc__ is None or not inspect.ismodule(package):
                continue
            docs[package_name] = self._parse_module_doc(package)
        
        return docs

    def _parse_module_doc(self, package):
        from libs.doc_parsers.module import Parser
        module_doc = Parser(self.package_root, package)()

        module_doc_exposes = []
        for exposes in module_doc.get('exposes', []):
            sub_exposes = exposes
            for method, callable_obj in exposes.get('exposes', {}).items():
                sub_exposes['exposes'][method] = self._parse_callable_doc(callable_obj)
            module_doc_exposes.append(sub_exposes)
        
        module_doc['exposes'] = module_doc_exposes
        
        return module_doc
    
    def _parse_callable_doc(self, callable_obj):
        from libs.doc_parsers.callable import Parser
        callable_doc = Parser(self.package_root, callable_obj)()
        return callable_doc

    def __call__(self, command, **kwargs):
        cmd = f'cmd_{command}'
        if not hasattr(self, cmd):
            cmd = 'cmd_help'
            kwargs['reason'] = f'暂不支持 {cmd!r} 命令'
        
        getattr(self, cmd)(**kwargs)
    

def main(argv: typing.Optional[list] = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'command',
        metavar="command",
        type=str,
        help="工具箱里具体指命令",
        default='help',
    )
    args = parser.parse_args(argv)
    t = Tools()
    t(args.command)

if __name__ == '__main__':
    main()