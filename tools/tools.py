import click, os

class Tools(object):
    def __init__(self) -> None:
        self.proj_dir = os.path.dirname(os.path.dirname(__file__))

    def _get_version():
        return 'lastest'

    def _gen_readme(self, version_changelog):
        readmetpl = os.path.join(self.proj_dir, 'tools', 'README.tpl.md')
        readme = os.path.join(self.proj_dir, 'README.md')

        with open(readmetpl, 'r') as rmtpl, open(readme, 'w') as rm:
            import re
            regex = re.compile('.*(\{\{__(?P<field>.*)__\}\})')
            while True:
                line = rmtpl.readline()
                matched = regex.match(line)
                if matched:
                    key = matched.groupdict()['field']
                    search = matched.group(1)
                    if key in version_changelog:
                        replace = version_changelog[key]
                        line = line.replace(search, replace)
                
                rm.write(line)
                if not line:
                    break

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

        self._gen_readme(version_changelog)
        
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
    def _init(command: str, **kwargs):
        method = f'cmd_{command}'
        getattr(tools, method)(**kwargs)
    
    _init()

if __name__ == '__main__':
    tools_main()