import click, os, typing 

class Tools(object):
    def __init__(self) -> None:
        self.proj_dir = os.path.dirname(os.path.dirname(__file__))

    def _gen_file(
            self, tpl_file, gen_file,
            content: dict, recover: bool = True
        ):
        tpl = os.path.join(self.proj_dir, 'tools', 'tpl', tpl_file)
        gen_file = os.path.join(self.proj_dir, gen_file)
        if not recover and os.path.exists(gen_file):
            return
        with open(tpl, 'r') as tplfile, open(gen_file, 'w') as gfile:
            import re
            regex = re.compile('.*(\{\{__(?P<field>.*)__\}\})')
            for line in tplfile:
                matched = regex.match(line)
                write_lines = []
                if matched:
                    key = matched.groupdict()['field']
                    search = matched.group(1)
                    if key in content:
                        replaces = content[key] if isinstance(content[key], list) else [content[key]]
                        for replace in replaces:
                                write_lines.append(line.replace(search, replace))
                    else:
                        write_lines.append(line)
                else:
                    write_lines.append(line)

                gfile.writelines(write_lines)
        
    def cmd_readme(self, **kwargs):
        project_dir = self.proj_dir
        version_changelog = {
            'version': 'latest',
            'changelog': '',
            'requirement': '',
        }
        with open(f'{project_dir}/changelog.md') as changelog:
            while True:
                line = changelog.readline().strip()
                if line.startswith('# v'):
                    version_changelog['version'] = line.replace('# v', '')
                elif line == '':
                    break
                else:
                    version_changelog['changelog'] += line + '\n'
        
        with open(f'{project_dir}/requirement.txt') as requiremt:
            for line in requiremt:
                line = line.strip()
                if line == '' or line.startswith('#'):
                    continue
                version_changelog['requirement'] += line + '\n'

        self._gen_file('README.tpl.md', 'README.md', version_changelog)

    def cmd_mkdoc(self):
        mkdoc_content = {
            'nav_item': '',
        }
        nav_items_ = []
        scan_path = os.path.join(self.proj_dir, 'yaa')
        for inode_name in os.listdir(scan_path):
            if inode_name in ('__pycache__'):
                continue

            if inode_name.endswith('.py') and inode_name not in ('__init__.py'):
                file_name = inode_name.replace('.py', '')
                nav_title = file_name.title().replace('_', '')
                nav_items_.append(
                        f"- {nav_title}: "
                        f"'{file_name}.md'"
                    )
        mkdoc_content['nav_item'] = nav_items_
        mkdoc_tpl = os.path.join(self.proj_dir, 'tools', 'tpl', 'mkdocs.tpl.yml')
        mkdoc = os.path.join(self.proj_dir, 'mkdocs.yml')
        self._gen_file('mkdocs.tpl.yml', 'mkdocs.yml', mkdoc_content)

    def cmd_pkgs(self, **kwargs) -> None:
        pkgs = []
        scan_path = os.path.join(self.proj_dir, 'yaa')
        for inode_name in os.listdir(scan_path):
            if inode_name in ('__pycache__'):
                continue

            if inode_name.endswith('.py') and inode_name not in ('__init__.py'):
                file_name = inode_name.replace('.py', '')
                self.cmd_docs(package=f'yaa.{file_name}')

    def cmd_docs(self, package: str = '', recover: bool=False):
        pkg = 'yaa.staticfiles'
        import importlib
        importlib.sys.path.append(os.path.join(self.proj_dir))
        try:
            mod = importlib.import_module(package)
            doc_file, content = self.gen_doc_content(mod)
            self._gen_file('nav_item.tpl.md', doc_file, content, recover)
        except ModuleNotFoundError:
            print(f'pkg {pkg} not found')

    def cmd_method_doc(self):
        import os, sys
        project_path = os.path.dirname(os.path.dirname(__file__))
        sys.path.append(project_path)
        from yaa import Yaa
        import inspect

        app = Yaa()

        attrs = [
            attr_name
            for attr_name in app.__dir__()
            if not attr_name.startswith('_') and inspect.ismethod(getattr(app, attr_name))
        ]

        for attr_name in attrs:
            self.parse_method_doc(app, attr_name)
    
    def parse_method_doc(self, app, method_name):
        import inspect
        from pprint import PrettyPrinter
        pp = PrettyPrinter(depth=6)

        method = getattr(app, method_name)
        
        methods_docs = {
            'title': '',
            'args': [],
            'raises': [],
            'returns': [],
            'examples': [],
        }
        key = ''
        
        def doc_line_args(doc_line):
            if ':' in doc_line.strip():
                (_name, _desc) = doc_line.strip().split(':', 1)
            else:
                _name, _desc = doc_line.strip(), None
            return _name, _desc
        
        def doc_line_raises(doc_line):
            return doc_line_args(doc_line)
        
        def doc_line_returns(doc_line):
            return doc_line_args(doc_line)
        
        def doc_line_examples(doc_line):
            return doc_line

        doc_line_handles = {
            'args': doc_line_args,
            'returns': doc_line_returns,
            'raises': doc_line_raises,
            'examples': doc_line_examples,
        }

        for idx, doc_line in enumerate((method.__doc__ or '').split('\n')):
            if idx == 0:
                methods_docs['title'] = doc_line.strip()
            else:
                if doc_line.strip() in ('Args:', 'Returns:', 'Raises:', 'Examples:'):
                    key = doc_line.strip().lower().strip(':')
                elif doc_line.strip() == '':
                    continue
                elif doc_line.strip():
                    fn = doc_line_handles[key]
                    methods_docs[key].append(fn(doc_line))

        pp.pprint(methods_docs)
        method_sig = inspect.signature(method)
        for _name, _p_sig in method_sig.parameters.items():
            pp.pprint(f'{_p_sig.name}:{_p_sig._kind}:{_p_sig}')


    def gen_doc_content(self, mod):
        doc_file = mod.__file__.replace(
                os.path.join(self.proj_dir, 'yaa'),
                'docs'
            ).replace('.py', '.md')

        content = self.parse_mod_doc(mod.__doc__)
        content.update({'python_code': '#'})
        return doc_file, content

    def parse_mod_doc(self, doc: str = ''):
        import re
        if doc is None:
            doc = ''
        content = {}
        key, value = None, None
        regex_field = re.compile('^\s*(?P<key>[\w]+)\s*:(?P<content>.*)')
        regex_line = re.compile('^(?P<start>[\s]{2,})(?P<content>.*)')
        for line in doc.split('\n'):
            if line.strip('') == '':
                continue
            field_matched = regex_field.match(line)
            if field_matched:
                if key is not None:
                    content[key] = value
                key = field_matched.groupdict()['key']
                value = field_matched.groupdict()['content'].strip()
            if key is not None: 
                line_matched = regex_line.match(line)
                if line_matched:
                    value += (
                        ('<br/>' if value != '' else '') +
                        line_matched.groupdict()['content'].strip()
                    )
        if key is not None:
            content[key] = value
        return content


    def cmds(cls):
        return [
                fn.replace('cmd_', '') 
                for fn in cls.__dir__()
                if str(fn).startswith('cmd_')
            ]

def main():
    tools = Tools()

    @click.command()
    @click.option('-cmd', '--command', prompt='command', help='which command you want to run', default='help', type=click.Choice(tools.cmds()))
    def _init(command: str, **kwargs):
        method = f'cmd_{command}'
        getattr(tools, method)(**kwargs)
    
    _init()

if __name__ == '__main__':
    main()