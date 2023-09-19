import click, os

class Tools(object):
    def __init__(self) -> None:
        self.proj_dir = os.path.dirname(os.path.dirname(__file__))

    def cmd_release_note(self):
        project_dir = self.proj_dir
        version_changelog = {
            'version': 'latest',
            'changelog': ''
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

        readmetpl = os.path.join(project_dir, 'tools', 'README.tpl.md')
        readme = os.path.join(project_dir, 'README.md')

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
    #end def release_note

    def cmd_doc(self) -> None:
        return


    def cmd_help(self):
        pass
    
    def cmds(cls):
        return [
                fn.replace('cmd_', '') 
                for fn in cls.__dir__()
                if str(fn).startswith('cmd_')
            ]

if __name__ == '__main__':
    tools = Tools()

    @click.command()
    @click.option('-cmd', '--command', prompt='command', help='which command you want to run', default='help', type=click.Choice(tools.cmds()))
    def _init(command: str, **kwargs):
        method = f'cmd_{command}'
        getattr(tools, method)(**kwargs)
    
    _init()