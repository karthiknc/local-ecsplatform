#!/usr/bin/python

import argparse
import os
import shutil
import subprocess
import socket
import filecmp

from local_config import sites, github

VERSION = '1.0.0'


class Build:
	"""Local ECS Platform builder."""

	def __init__(self):
		"""Set defaults and init arguments parser."""
		self.args = None
		self.build = False
		self._backup_files = {}
		self.parse_args()

	def parse_args(self):
		"""
		Parse arguments.

		:return: None
		"""
		parser = argparse.ArgumentParser()
		parser.add_argument('build_ecs', nargs='?', default='0', help='Build ECS Image | 0: Skip | 1: Build')
		parser.add_argument('build_wpp', nargs='?', default='0', help='Build WPP Image | 0: Skip | 1: Build')
		parser.add_argument('build_site', nargs='?', default='0', help='Build Site Image | 0: Skip | 1: Build')
		parser.add_argument('-s', '--symlink', action='store_true', help='Rebuild sites\' symlinks')
		parser.add_argument('-v', '--version', action='store_true', help='Current version')
		parser.add_argument('-vv', '--verbose', action='store_true', help='Output more info about build')
		parser.add_argument('-sk', '--skip_download', action='store_true', help='Skip Download dockerfiles')
		parser.add_argument('-od', '--only_download', action='store_true', help='Only Download dockerfiles')
		parser.add_argument('-p', '--prepare_ssl', action='store_true', help='Prepare proxy ssl service')
		self.args = parser.parse_args()

	def vprint(self, message):
		"""
		Print if verbose argument is set.

		:param message: Print message.
		:return: None
		"""
		if self.args.verbose:
			print message

	def install_docker_sync(self):
		"""
		Install docker-sync -> http://docker-sync.io/ Requires sudo.

		:return: None
		"""
		print 'Installing docker-sync'
		try:
			self.vprint('Checking if docker-sync exists')
			subprocess.call(['docker-sync-stack', '--version'])
		except OSError:
			self.vprint('Running gem install docker-sync')
			subprocess.call(['gem', 'install', 'docker-sync'])

	def build_docker_compose(self):
		"""
		Build Docker Compose file.

		Copy docker-compose.yml to root directory and
		Add site themes volumes under `site` service

		:return: None
		"""
		print 'Building docker-compose.yml and docker-sync.yml'

		self.vprint('Copying `src/docker-compose.yml` to `docker-compose.yml`')
		# Todo: Be careful. This will override old docker-compose.yml and docker-sync.yml
		shutil.copy(os.path.abspath('src/docker-compose.yml'), os.path.abspath('docker-compose.yml'))

		self.vprint('Copying `src/docker-sync.yml` to `docker-sync.yml`')
		shutil.copy(os.path.abspath('src/docker-sync.yml'), os.path.abspath('docker-sync.yml'))

		# Add mount sites themes volume to docker compose.
		self.vprint('Opening docker-compose.yml and docker-sync.yml for editing')

		with open('docker-compose.yml', 'r+') as compose_file, open('docker-sync.yml', 'r+') as sync_file:
			compose_lines = compose_file.readlines()
			sync_lines = sync_file.readlines()

			vol_index = compose_lines.index('            - site-sync:/var/www/html:nocopy\n')
			sync_src_index = sync_lines.index('        src: ./wp\n')

			for site in reversed(sites):
				volume_name = 'theme-{}-sync'.format(site['theme'].split('/')[-1])
				theme_path = '{}/{}'.format(site['path'], site['theme'])

				self.vprint('Adding {} under site volumes'.format(theme_path))
				compose_lines.insert(vol_index + 1, '            - {}:{}:nocopy\n'
								.format(volume_name, os.path.abspath(theme_path)))

				self.vprint('Adding volume definitions for {}'.format(volume_name))
				vol_def_index = compose_lines.index('    site-sync:\n')
				compose_lines.insert(vol_def_index + 2, '    {}:\n'.format(volume_name))
				compose_lines.insert(vol_def_index + 3, '        external: true\n')

				self.vprint('Adding sync definitions for {}'.format(volume_name))
				sync_lines.insert(sync_src_index + 1, '    {}:\n'.format(volume_name))
				sync_lines.insert(sync_src_index + 2, '        src: {}\n'.format(theme_path))

			self.vprint('Moving docker-compose file pointer to 0')
			compose_file.seek(0)

			self.vprint('Writing compose_lines')
			compose_file.writelines(compose_lines)

			self.vprint('Truncating old lines and closing')
			compose_file.truncate()

			self.vprint('Moving docker-sync file pointer to 0')
			sync_file.seek(0)

			self.vprint('Writing sync_lines')
			sync_file.writelines(sync_lines)

			self.vprint('Truncating old lines and closing')
			sync_file.truncate()

	def create_symlinks(self):
		"""
		Create theme symbolic links.

		:return: None
		"""
		self.vprint('Making directories: wp/wp-content/themes')

		subprocess.call(['mkdir', '-p', 'wp/wp-content/themes'])

		for site in reversed(sites):
			src_path = '{}/{}'.format(site['path'], site['theme'])
			dst_path = 'wp/wp-content/themes/{}'.format(site['theme'].split('/')[-1])

			print 'Creating symbolic links: {} -> {}'.format(dst_path, src_path)
			try:
				os.symlink(os.path.abspath(src_path), os.path.abspath(dst_path))
			except OSError:
				print '{} Symlink already exists.'.format(dst_path)

	def prepare_ssl_proxy(self):
		"""
		Prepare v3.ext file for ssl certificate, (re)starts proxy service.

		:return: None
		"""
		print 'Preparing ssl proxy'
		self.vprint('Creating directories: volumes/certificates')
		subprocess.call(['mkdir', '-p', 'volumes/certificates'])

		if os.path.isfile('volumes/certificates/v3.ext'):
			self.vprint('Creating backup: volumes/certificates/v3.ext.bak')
			shutil.copy(os.path.abspath('volumes/certificates/v3.ext'),
						os.path.abspath('volumes/certificates/v3.ext.bak'))

		self.vprint('Copying src/ssl/v3.ext to volumes/certificates/v3.ext')
		shutil.copy(os.path.abspath('src/ssl/v3.ext'), os.path.abspath('volumes/certificates/v3.ext'))

		with open('volumes/certificates/v3.ext', 'r+') as ssl_file:
			lines = ssl_file.readlines()
			dns_index = lines.index('DNS.2 = *.local\n')

			i = len(sites) + 2
			for site in reversed(sites):
				self.vprint('Adding DNS entry for {}'.format(site['local_url']))
				lines.insert(dns_index + 1, 'DNS.{} = {}\n'.format(i, site['local_url']))
				i -= 1

			self.vprint('Moving file pointer to 0')
			ssl_file.seek(0)

			self.vprint('Writing lines')
			ssl_file.writelines(lines)

			self.vprint('Truncating old lines and closing')
			ssl_file.truncate()

		self.vprint('Comparing volumes/certificates/v3.ext and backup')
		identical = filecmp.cmp(os.path.abspath('volumes/certificates/v3.ext'),
					os.path.abspath('volumes/certificates/v3.ext.bak'))

		self.vprint('Deleting volumes/certificates/v3.ext.bak')
		os.remove('volumes/certificates/v3.ext.bak')

		if identical:
			self.vprint('volumes/certificates/v3.ext and backup are identical.')
			print 'SSL Proxy container is upto date.'
			return

		try:
			self.vprint('Deleting mounted certificate files')
			os.remove('volumes/certificates/key.pem')
			os.remove('volumes/certificates/csr.pem')
			os.remove('volumes/certificates/cert.pem')
		except OSError:
			self.vprint('No certificate files to delete.')

		try:
			self.vprint('Attempting to restart proxy with `docker-compose restart proxy`')
			subprocess.check_call(['docker-compose', 'restart', 'proxy'])
		except subprocess.CalledProcessError:
			self.vprint('`docker-compose restart proxy` failed.')
			self.vprint('Running `docker-compose up -d proxy`')
			subprocess.call(['docker-compose', 'up', '-d', 'proxy'])
		except OSError:
			pass  # docker-compose not found

		self.vprint('Attempting to trust ecslocal certificate. Requires administrator privilege.')
		subprocess.call(['sudo', './src/ssl/cert.sh', 'true'])

	def svn_export(self, path):
		"""
		Download files from nu-ecsplatform using svn export.

		:param path: Download file or folder path.
		:return: None
		"""
		if 'branch' not in github or github['branch'] == 'master':
			branch = 'trunk'
		else:
			branch = 'branches/{}'.format(github['branch'])

		url = 'https://github.com/newsuk/nu-ecsplatform.git/{}/{}'.format(branch, path)
		self.vprint('Downloading files:\n{}'.format(url))

		subprocess.call(
			['svn',
			 'export',
			 url,
			 '--username={}'.format(github['username']),
			 '--password={}'.format(github['access_token']),
			 '--non-interactive',
			 '--trust-server-cert'
			 ]
		)

	def download_dockerfiles(self):
		"""
		Remove old dockerfiles and Download fresh using svn_export.

		:return: None
		"""
		self.vprint('Deleting directory: dockerfiles')
		try:
			shutil.rmtree(os.path.abspath('dockerfiles'))
		except OSError:
			self.vprint('dockerfiles directory does not exists')

		self.vprint('Deleting specfile.json')
		try:
			os.remove(os.path.abspath('specfile.json'))
		except OSError:
			self.vprint('specfile.json does not exists')

		self.svn_export('ecsplatform/orchestrator/actors/build/dockerfiles')
		self.svn_export('ecsplatform/config/specfile.json')

	def arrange_files(self):
		"""
		Arrange files required for docker build.

		:return: None
		"""
		# Copy specfile.json to scripts
		if os.path.isfile('specfile.json'):
			self.vprint('Moving specfile.json to dockerfiles/03_site/scripts/')
			shutil.move(os.path.abspath('specfile.json'),
						os.path.abspath('dockerfiles/03_site/scripts/specfile.json'))

		# Copy local_start, entrypoint scripts and local sites config file to scripts.
		self.vprint('Copying src/scripts/local_start.py to dockerfiles/03_site/scripts/')
		shutil.copy(os.path.abspath('src/scripts/local_start.py'),
					os.path.abspath('dockerfiles/03_site/scripts/local_start.py'))

		self.vprint('Copying src/scripts/local_entrypoint.py to dockerfiles/03_site/scripts/')
		shutil.copy(os.path.abspath('src/scripts/local_entrypoint.py'),
					os.path.abspath('dockerfiles/03_site/scripts/local_entrypoint.py'))

		self.vprint('Copying local_config.py to dockerfiles/03_site/scripts/')
		shutil.copy(os.path.abspath('local_config.py'),
					os.path.abspath('dockerfiles/03_site/scripts/local_config.py'))

		# If skip download, restore backup files
		if self.args.skip_download and os.path.isdir('dockerfiles'):
			self.vprint('Restoring backup file dockerfiles/03_site/Dockerfile')
			shutil.copy(os.path.abspath('dockerfiles/03_site/Dockerfile.bak'),
						os.path.abspath('dockerfiles/03_site/Dockerfile'))

			self.vprint('Restoring backup file dockerfiles/03_site/scripts/run_startup.py')
			shutil.copy(os.path.abspath('dockerfiles/03_site/scripts/run_startup.py.bak'),
						os.path.abspath('dockerfiles/03_site/scripts/run_startup.py'))

	def backup_file(self, file_path):
		"""
		Backup given file with `.bak` suffix.

		:param file_path: File path to backup.
		:return: None
		"""
		file_abs_path = os.path.abspath(file_path)
		print 'Backing up {}'.format(file_abs_path)
		backup_file_path = '{}.bak'.format(file_abs_path)
		shutil.copy(file_abs_path, backup_file_path)
		self._backup_files[file_abs_path] = backup_file_path

	def backup_files(self):
		# Backup files if any. Not needed.
		pass

	def revert_backup(self):
		# Revert backup files. Not needed.
		for file_path, backup_path in self._backup_files.items():
			if os.path.isfile(file_path) and os.path.isfile(backup_path):
				print 'Reverting {}'.format(file_path)
				os.remove(file_path)
				shutil.move(backup_path, file_path)

	def prepare_site_dockerfile(self):
		"""
		Prepare site Dockerfile.

		:return: None
		"""
		print 'Preparing site dockerfile'
		self.vprint('Opening dockerfiles/03_site/Dockerfile')

		hostname = socket.gethostname()
		host_ip = socket.gethostbyname(hostname)

		with open('dockerfiles/03_site/Dockerfile', 'r+') as start_file:
			removable_lines = []
			lines = start_file.readlines()

			for index, line in enumerate(lines):
				if 'RUN git clone' in line:
					self.vprint('Removing line with `RUN git clone`')
					removable_lines.append(index)

				elif 'mv @SITE_REPO@' in line:
					self.vprint('Removing line with `mv @SITE_REPO@`')
					removable_lines.append(index)

				elif 'rm -rf @SITE_REPO@' in line:
					self.vprint('Removing line with `rm -rf @SITE_REPO@`')
					removable_lines.append(index)

			lines = [i for j, i in enumerate(lines) if j not in removable_lines]

			self.vprint('Replacing line `build_site @{TOKENS}@` with `build_site {VALUES}`')
			build_index = lines.index('    build_site @SITE_REPO@ @THEME@ @SITE_PATH@ @URL@ @ADMIN_PASS@ && \\\n')
			lines[build_index] = '    build_site local-wp basic-theme / localhost wp-admin && \\\n'

			self.vprint('Adding line with `install vim xdebug && mv html to html-copy`')
			lines.insert(len(lines), 'RUN apt-get update && apt-get install -y --no-install-recommends '
									 'php7.3-xdebug vim nano -y && phpenmod xdebug && mkdir -p /var/www/html-copy && '
									 'mv /var/www/html/* /var/www/html-copy && \\\n')
			lines.insert(len(lines), '    echo "zend_extension=$(find /usr/lib/php/2018* -name xdebug.so)"'
									 ' > /etc/php/7.3/mods-available/xdebug.ini && \\\n')
			lines.insert(len(lines),
						 '    echo "xdebug.default_enable = 0" >> /etc/php/7.3/mods-available/xdebug.ini && \\\n')
			lines.insert(len(lines),
						 '    echo "xdebug.remote_enable = 1" >> /etc/php/7.3/mods-available/xdebug.ini && \\\n')
			lines.insert(len(lines),
						 '    echo "xdebug.idekey = PHPSTORM" >> /etc/php/7.3/mods-available/xdebug.ini && \\\n')
			lines.insert(len(lines),
						 '    echo "xdebug.remote_connect_back = 0" >> /etc/php/7.3/mods-available/xdebug.ini && \\\n')
			lines.insert(len(lines),
						 '    echo "xdebug.remote_port = 9000" >> /etc/php/7.3/mods-available/xdebug.ini && \\\n')
			lines.insert(len(lines), '    echo "xdebug.remote_host = {}" >> '
						 '/etc/php/7.3/mods-available/xdebug.ini\n'.format(host_ip))

			self.vprint('Adding line with `CMD local_entrypoint.py && supervisord`')
			lines.insert(len(lines),
						 'CMD python /build/scripts/local_entrypoint.py && /bin/sh -c /usr/bin/supervisord\n')

			self.vprint('Moving file pointer to 0')
			start_file.seek(0)

			self.vprint('Writing lines')
			start_file.writelines(lines)

			self.vprint('Truncating old lines and closing')
			start_file.truncate()

	def prepare_startup_file(self):
		"""
		Add startup python script for local setup to startup script.

		:return: None
		"""
		print 'Preparing site dockerfile'
		self.vprint('Opening dockerfiles/03_site/scripts/run_startup.py')

		with open('dockerfiles/03_site/scripts/run_startup.py', 'r+') as start_file:
			lines = start_file.readlines()
			start_index = lines.index('from environment import Environment\n')

			self.vprint('Adding line with `from local_start import LocalStart`')
			lines.insert(start_index + 1, '\nfrom local_start import LocalStart\n')

			run_index = lines.index('def run():\n')

			self.vprint('Adding line with `LocalStart().run()`')
			lines.insert(run_index + 1, '\n    LocalStart().run()\n')

			self.vprint('Moving file pointer to 0')
			start_file.seek(0)

			self.vprint('Writing lines')
			start_file.writelines(lines)

			self.vprint('Truncating old lines and closing')
			start_file.truncate()

	def build_each_image(self):
		"""
		Build docker images based on given arguments.

		:return: None
		"""
		if self.args.build_ecs == 'true' or self.args.build_ecs == '1':
			print 'Building ECSP Image'
			subprocess.call(['docker', 'build', './dockerfiles/01_ecsp/', '--tag', 'nu-ecs-platform:latest'])

		if self.args.build_wpp == 'true' or self.args.build_wpp == '1':
			print 'Building WPP Image'
			subprocess.call(['docker', 'build', './dockerfiles/02_wpp/', '--tag', 'nu-wp-platform:latest'])

		if self.args.build_site == 'true' or self.args.build_site == '1':
			print 'Building Site Image'
			subprocess.call(['docker', 'build', './dockerfiles/03_site/', '--tag', 'nu-wp-site:latest'])

	def build_images(self):
		"""
		Build images manager.

		:return: None
		"""
		print 'Building docker images'

		self.install_docker_sync()

		if self.args.skip_download and os.path.isdir('dockerfiles'):
			self.vprint('Skipping download dockerfiles')
		else:
			print 'Downloading dockerfiles'
			self.download_dockerfiles()
			self.backup_file('dockerfiles/03_site/Dockerfile')
			self.backup_file('dockerfiles/03_site/scripts/run_startup.py')

		self.arrange_files()
		self.prepare_site_dockerfile()
		self.prepare_startup_file()
		self.build_each_image()
		self.create_symlinks()
		self.build_docker_compose()

	def start_containers(self):
		"""
		Start docker-sync, Start services with docker-compose.

		:return: None
		"""
		subprocess.call(['docker-sync', 'start'])
		subprocess.call(['docker-compose', 'up', '-d'])

	def run(self):
		"""
		Run builder.

		If build_ecs or build_wpp or build_site arguments are true,
		Prepare required files and build images.
		If version argument is true print current builder version.
		If symlink argument is true rebuild symlinks and docker-compose.yml.

		:return: None
		"""
		if self.args.build_ecs == '1' or \
				self.args.build_wpp == '1' or \
				self.args.build_site == '1':
			self.build = True

		if self.args.version:
			print VERSION

		if self.args.symlink and not self.build:
			self.create_symlinks()
			self.build_docker_compose()

		if self.args.only_download:
			print 'Downloading dockerfiles'
			self.download_dockerfiles()
			self.backup_file('dockerfiles/03_site/Dockerfile')
			self.backup_file('dockerfiles/03_site/scripts/run_startup.py')

		if self.args.prepare_ssl:
			self.prepare_ssl_proxy()

		if self.build:
			self.build_images()


if __name__ == '__main__':
	Build().run()
