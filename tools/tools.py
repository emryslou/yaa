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
        
    def cmd_readme(self):
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
                    version_changelog['changelog'] += line
        
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
        scan_path = os.path.join(self.proj_dir, 'yast')
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
        scan_path = os.path.join(self.proj_dir, 'yast')
        for inode_name in os.listdir(scan_path):
            if inode_name in ('__pycache__'):
                continue

            if inode_name.endswith('.py') and inode_name not in ('__init__.py'):
                file_name = inode_name.replace('.py', '')
                self.cmd_docs(package=f'yast.{file_name}')

    def cmd_docs(self, package: str = '', recover: bool=False):
        pkg = 'yast.staticfiles'
        import importlib
        importlib.sys.path.append(os.path.join(self.proj_dir))
        try:
            mod = importlib.import_module(package)
            doc_file, content = self.gen_doc_content(mod)
            self._gen_file('nav_item.tpl.md', doc_file, content, recover)
        except ModuleNotFoundError:
            print(f'pkg {pkg} not found')
    
    def gen_doc_content(self, mod):
        doc_file = mod.__file__.replace(
                os.path.join(self.proj_dir, 'yast'),
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

def tools_main():
    tools = Tools()

    @click.command()
    @click.option('-cmd', '--command', prompt='command', help='which command you want to run', default='help', type=click.Choice(tools.cmds()))
    @click.option('-r', '--recover', prompt='recover', help='', default=False, type=bool)
    @click.option('-pkg', '--package', prompt='package', help='package',  default='', type=str)
    def _init(command: str, **kwargs):
        method = f'cmd_{command}'
        getattr(tools, method)(**kwargs)
    
    _init()

if __name__ == '__main__':
    tools_main()