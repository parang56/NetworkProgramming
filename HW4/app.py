# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, SubmitField
from wtforms.validators import DataRequired
import random
from flask_wtf.csrf import CSRFProtect
from game_db import init_db, get_db_connection

app = Flask(__name__)
app.secret_key = 'your_secret_key'
csrf = CSRFProtect(app)
init_db()

# Hardcoded users
users = {
    'user1': 'password1',
    'user2': 'password2',
    'user3': 'password3'
}


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class GuessForm(FlaskForm):
    guess = StringField('Enter your guess:',
                        validators=[DataRequired()])  # Changed to StringField to handle non-numeric input
    submit = SubmitField('Submit')


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        if username in users and users[username] == password:
            session['username'] = username

            # Check if user exists in the database and create if not
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            if not user:
                cursor.execute('INSERT INTO users (username, password, score) VALUES (?, ?, ?)',
                               (username, password, 0))
                conn.commit()

            # Create a new game entry in the database
            cursor.execute('''
                INSERT INTO games (user_id, number, attempts, finished) 
                VALUES (?, ?, ?, ?)
            ''', (username, random.randint(1, 10), 0, 0))
            conn.commit()
            conn.close()

            return redirect(url_for('game'))
        else:
            flash('Invalid credentials', 'error')
    return render_template('login.html', form=form)


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/game', methods=['GET', 'POST'])
def game():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch user score
    cursor.execute('SELECT score FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    score = user['score'] if user else 0

    # Fetch or create a new game entry
    cursor.execute('''
        SELECT * FROM games WHERE user_id = ? AND finished = 0
    ''', (username,))
    game = cursor.fetchone()

    if not game:
        cursor.execute('''
            INSERT INTO games (user_id, number, attempts, finished) 
            VALUES (?, ?, ?, ?)
        ''', (username, random.randint(1, 10), 0, 0))
        conn.commit()
        cursor.execute('''
            SELECT * FROM games WHERE user_id = ? AND finished = 0
        ''', (username,))
        game = cursor.fetchone()

    form = GuessForm()
    message = ""
    if form.validate_on_submit():
        try:
            guess = int(form.guess.data)
            if guess < 0 or guess > 10:
                raise ValueError
        except ValueError:
            flash("Your input needs to be a number between 0 and 10!")
        else:
            attempts = game['attempts'] + 1
            number = game['number']
            game_id = game['id']

            if guess == number:
                message = "Congratulations, you did it."
                cursor.execute('''
                    UPDATE games SET attempts = ?, finished = 1 WHERE id = ?
                ''', (attempts, game_id))

                # Update user score
                cursor.execute('''
                    UPDATE users SET score = score + 1 WHERE username = ?
                ''', (username,))
                conn.commit()
                score += 1  # Update local score variable

            elif guess < number:
                message = "Hint: You guessed too small!"
            else:
                message = "Hint: You guessed too high!"

            if attempts >= 5 and guess != number:
                message = "Sorry, you've used all your attempts!"
                cursor.execute('''
                    UPDATE games SET attempts = ?, finished = 1 WHERE id = ?
                ''', (attempts, game_id))
            else:
                cursor.execute('''
                    UPDATE games SET attempts = ? WHERE id = ?
                ''', (attempts, game_id))

            conn.commit()
            flash(message)

    cursor.execute('''
        SELECT * FROM games WHERE user_id = ? AND finished = 0
    ''', (username,))
    game = cursor.fetchone()
    attempts = game['attempts'] if game else 0

    conn.close()

    # Initial message when the game starts
    if attempts == 0:
        flash(
            "You have a total of 5 attempts. Guess a number between 1 to 10:")

    return render_template('game.html', form=form, attempts=attempts, score=score)


if __name__ == '__main__':
    app.run(debug=True)
