#!/usr/bin/python

import os
import sys
import shutil
import subprocess

from local_config import sites

# Platform build automator.
#
# Supply arguments:
# First parameter: Bool - Build ECS Platform Image
# Second parameter: Bool - Build WP Platform Image
# Third parameter: Bool - Build site Image
# Example: ./build.py true true true

if len(sys.argv) < 4:
	print '\033[1mProvide at least 3 arguments\033[0m'
	print '\tFirst parameter: Bool - Whether to build ECS Platform Image'
	print '\tSecond parameter: Bool - Whether to build WP Platform Image'
	print '\tThird parameter: Bool - Whether to build site Image'
	print '\texample 1: ./build.py true true true'
	print '\texample 1: ./build.py 0 0 1'
	exit(1)

# Creating symlinks required for Docker Volume.
# for site in sites:
# 	print "Adding {} symlink to Docker volumes".format(site['path'])
# 	theme_path = os.path.abspath('{}/src/themes/{}'.format(site['path'], site['theme']))
# 	docker_volume_path = os.path.abspath('./themes/{}'.format(site['theme']))
# 	if not os.path.isdir(docker_volume_path):
# 		os.makedirs('themes')
# 	try:
# 		os.symlink(theme_path, docker_volume_path)
# 	except OSError:
# 		print '\tSymlink already exists'

# Todo: download dockerfiles from github:
# Todo: svn ls https://github.com/newsuk/nu-ecsplatform.git/trunk/ecsplatform/orchestrator/actors/build/dockerfiles
# --username=user --password=pass
subprocess.call(
	['svn',
	'export',
	'https://github.com/newsuk/nu-ecsplatform.git/trunk/ecsplatform/orchestrator/actors/build/dockerfiles',
	'--username=user',
	'--password=pass',
	'--non-interactive',
	'--trust-server-cert'
	]
)

backup_files = {}


# Keep record of backup files.
def backup_file(file_abs_path):
	print 'Backing up {}'.format(file_abs_path)
	backup_file_path = '{}.bak'.format(file_abs_path)
	shutil.copy(file_abs_path, backup_file_path)
	backup_files[file_abs_path] = backup_file_path


backup_file(os.path.abspath('dockerfiles/03_site/Dockerfile'))
backup_file(os.path.abspath('03_site/startup.sh'))


def prepare_site_dockerfile():
	with open('dockerfiles/03_site/Dockerfile', 'r+') as start_file:
		removable_lines = []
		lines = start_file.readlines()
		for index, line in enumerate(lines):
			if 'RUN git clone' in line:
				removable_lines.append(index)
			elif 'mv @SITE_REPO@' in line:
				removable_lines.append(index)
			elif 'rm -rf @SITE_REPO@' in line:
				removable_lines.append(index)
		lines = [i for j, i in enumerate(lines) if j not in removable_lines]
		build_index = lines.index('    build_site @SITE_REPO@ @THEME@ @SITE_PATH@ @URL@ @ADMIN_PASS@\n')
		lines[build_index] = '    build_site local-wp twentynineteen / localhost wp-admin\n'
		start_file.seek(0)
		start_file.writelines(lines)
		start_file.truncate()

prepare_site_dockerfile()


# Add startup python script for local setup to startup script.
with open('03_site/startup.sh', 'r+') as start_file:
	lines = start_file.readlines()
	start_index = lines.index('#!/bin/bash\n')
	lines.insert(start_index + 1, '\npython /var/www/html/scripts/local_start.py\n')
	start_file.seek(0)
	start_file.writelines(lines)
	start_file.truncate()

# Copy sites config file required for local start script.
shutil.copy(os.path.abspath('local_config.py'), os.path.abspath('src/scripts/local_config.py'))

# Copy docker-compose.yml to root dir.
# Todo: Be careful. This will override old docker-compose.yml
shutil.copy(os.path.abspath('src/docker-compose.yml'), os.path.abspath('docker-compose.yml'))

# Add mount sites themes volume to docker compose.
with open('docker-compose.yml', 'r+') as compose_file:
	lines = compose_file.readlines()
	vol_index = lines.index('            - ./src/scripts:/var/www/html/scripts\n')
	for site in reversed(sites):
		theme_path = '{}/src/themes/{}'.format(site['path'], site['theme'])
		lines.insert(vol_index + 1, '            - {}:/var/www/html/wp-content/themes/{}\n'
															.format(theme_path, site['theme']))
	compose_file.seek(0)
	compose_file.writelines(lines)
	compose_file.truncate()

# Build docker images.
if sys.argv[1] == 'true' or sys.argv[1] == '1':
	print 'Building ECSP Image'
	subprocess.call(['docker', 'build', './01_ecsp/', '--tag', 'nu-ecs-platform:latest'])

if sys.argv[2] == 'true' or sys.argv[2] == '1':
	print 'Building WPP Image'
	subprocess.call(['docker', 'build', './02_wpp/', '--tag', 'nu-wp-platform:latest'])

if sys.argv[3] == 'true' or sys.argv[3] == '1':
	print 'Building Site Image'
	subprocess.call(['docker', 'build', './03_site/', '--tag', 'nu-wp-site:latest'])

# Revert backup files.
for file_path, backup_path in backup_files.items():
	if os.path.isfile(file_path) and os.path.isfile(backup_path):
		print 'Reverting {}'.format(file_path)
		os.remove(file_path)
		shutil.move(backup_path, file_path)
