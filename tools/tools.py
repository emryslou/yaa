import os
project_dir = os.path.dirname(os.path.dirname(__file__))
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