import functools

from flask import (
	Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from tbdr.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=('GET', 'POST'))
def register():
	if request.method == 'POST':
		print(request.form)
		forename = request.form['forename'].title()
		surname = request.form['surname'].title()
		institution = request.form['institution'].lower()
		country = request.form['country'].title()
		username = request.form['email_address']
		password = request.form['password']
		password_redo = request.form['password_redo']
		db = get_db()
		error = None

		if None in [forename,surname,institution,country,username,password,password_redo]:
			error = 'Please fill in all boxes'
		elif password!=password_redo:
			error = 'Passwords do not match'
		elif db.execute(
			'SELECT id FROM user WHERE username = ?', (username,)
		).fetchone() is not None:
			error = 'User {} is already registered.'.format(username)

		if error is None:
			db.execute(
				'INSERT INTO users (username, forename, surname, password, institution, country) VALUES (?, ?, ?, ?, ?, ?)',
				(username, forename, surname, generate_password_hash(password), institution, country)
			)
			db.commit()
			return redirect(url_for('auth.login'))

		flash(error)

	return render_template('auth/register.html')


@bp.route('/login', methods=('GET', 'POST'))
def login():
	if request.method == 'POST':
		username = request.form['username']
		password = request.form['password']
		print("Trying to log in: %s" % username)
		db = get_db()
		error = None
		user = db.execute(
			'SELECT * FROM users WHERE username = ?', (username,)
		).fetchone()

		if user is None:
			error = 'Incorrect username.'
		elif not check_password_hash(user['password'], password):
			error = 'Incorrect password. |%s| |%s|' % (user['password'],password)

		if error is None:
			session.clear()
			session['user_id'] = user['id']
			print(user['id'])
			return redirect(url_for('home.index'))

		flash(error)

	return render_template('auth/login.html')

@bp.before_app_request
def load_logged_in_user():
	user_id = session.get('user_id')

	if user_id is None:
		g.user = None
	else:
		g.user = get_db().execute(
			'SELECT * FROM users WHERE id = ?', (user_id,)
		).fetchone()

@bp.route('/logout')
def logout():
	session.clear()
	return redirect(url_for('home.index'))


def login_required(view):
	@functools.wraps(view)
	def wrapped_view(**kwargs):
		if g.user is None:
			return redirect(url_for('auth.login'))

		return view(**kwargs)

	return wrapped_view
