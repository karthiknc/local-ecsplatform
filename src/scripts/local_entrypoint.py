#!/usr/bin/python

import os
import shutil
import pwd
import grp
import subprocess


class LocalEntrypoint:
	def __init__(self):
		pass

	def revert_wp_files(self):
		all_files = os.listdir('/var/www/html-copy/')

		whitelist = [
			'wp-content',
			'.htaccess'
		]

		replace_files = [f for f in all_files if f not in whitelist]

		for file_name in replace_files:
			src_path = '/var/www/html-copy/{}'.format(file_name)
			dst_path = '/var/www/html/{}'.format(file_name)
			try:
				shutil.rmtree(dst_path)
			except OSError:
				print 'No file/folder to remove'

			shutil.move(src_path, dst_path)

	def chown_mounted_html(self):
		uid = pwd.getpwnam('www-data').pw_uid
		gid = grp.getgrnam('www-data').gr_gid
		path = '/var/www/html'

		for root, dirs, files in os.walk(path):
			for single_dir in dirs:
				os.chown(os.path.join(root, single_dir), uid, gid)
			for single_file in files:
				os.chown(os.path.join(root, single_file), uid, gid)

	def run(self):
		self.revert_wp_files()
		# Todo: Update wp-content directory.
		# chown is done in Dockerfile CMD as it is much faster.
		subprocess.call(['chown', '-R', 'www-data:www-data', '/var/www/html'])
		# self.chown_mounted_html()


if __name__ == "__main__":
	LocalEntrypoint().run()
