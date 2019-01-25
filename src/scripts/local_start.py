#!/usr/bin/python

import os
import shutil
import pwd
import grp
import subprocess
import json

from local_config import sites

uid = pwd.getpwnam('www-data').pw_uid
gid = grp.getgrnam('www-data').gr_gid

class LocalStart:
	def __init__(self):
		pass

	def move_update_artifacts(self):
		file_path = '/build/scripts/specfile.json'
		with open(file_path, 'r') as raw_file:
			specs = json.load(raw_file)
			specs['resources']['compute:ecs']['task']['container_definition'] = {
				'image': 'nu-wp-site:latest'
			}
		with open('/build/artifacts/specfile_updated.json', 'w') as out_file:
			json.dump(specs, out_file)

	def add_apache_site_configs(self):
		for site in sites:
			conf_path = '/etc/apache2/sites-available/{}.conf'.format(site['name'])
			shutil.copy('/etc/apache2/sites-available/000-default.conf', conf_path)

			with open(conf_path) as conf_file:
				lines = conf_file.readlines()
				server_name = lines.index('\t#ServerName www.example.com\n')
				lines[server_name] = '\tServerName {}\n'.format(site['local_url'])
				lines.insert(server_name + 1, '\tSetEnv DB_NAME {}\n'.format(site['db_name']))

				log_dir = '/var/log/apache2/{}'.format(site['name'])
				try:
					os.makedirs(log_dir)
					os.chown(log_dir, uid, gid)
				except OSError:
					print 'Log dir exists'

				error_log = lines.index('\tErrorLog /var/log/apache2/error.log\n')
				lines[error_log] = '\tErrorLog {}/error.log\n'.format(log_dir)

				access_log = lines.index('\tCustomLog /var/log/apache2/access.log combined\n')
				lines[access_log] = '\tCustomLog {}/access.log combined\n'.format(log_dir)

			with open(conf_path, 'w') as new_file:
				new_file.writelines(lines)

			subprocess.call(['a2ensite', site['name']])

		subprocess.call(['apachectl', '-k', 'restart'])

	def edit_wp_config(self):
		with open('/var/www/html/wp-config.php') as wp_conf_file:
			lines = wp_conf_file.readlines()
			try:
				db_name = lines.index("define('DB_NAME', getenv('WORDPRESS_DB_NAME'));\r\n")
			except ValueError:
				return
			lines[db_name] = "if ( isset( $_SERVER['DB_NAME'] ) ) {\r\n" \
							 "\tdefine('DB_NAME', $_SERVER['DB_NAME']);\r\n} else {\r\n" \
							 "\tdefine('DB_NAME', getenv('WORDPRESS_DB_NAME'));\r\n}\r\n"
		with open('/var/www/html/wp-config.php', 'w') as new_file:
			new_file.writelines(lines)

	def wp_initial_setup(self):
		for site in sites:
			# Todo: This is installing on localhost DB
			wp_path = '/var/www/html/'
			command = """
			if ! $(wp core is-installed --path={} --allow-root);
			then
				echo "Wordpress is not installed yet"
				wp core install --path={} --url={} --title={} --admin_user=root --admin_password=root \
				--admin_email=wordpress-platform@news.co.uk --allow-root
			else
				echo "Wordpress is already installed"
			fi
			""".format(wp_path, wp_path, site['local_url'], site['name'])
			subprocess.check_output(command, shell=True)

	def add_phpinfo(self):
		with open('/var/www/html/info.php', 'w') as info_file:
			info_file.write('<?php\nphpinfo();\n')

	def cleanup(self):
		# os.remove('/build/scripts/local_config.py')
		pass

	def run(self):
		self.move_update_artifacts()
		self.add_apache_site_configs()
		self.edit_wp_config()
		self.wp_initial_setup()
		self.add_phpinfo()
		self.cleanup()
