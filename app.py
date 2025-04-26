from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Database setup (SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.getenv('CLOUD_NAME'),
    api_key=os.getenv('API_KEY'),
    api_secret=os.getenv('API_SECRET')
)

# Import your models after db is initialized
# Example model (adjust according to your actual models)
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(200), nullable=True)

@app.route('/', methods=['GET'])
def home():
    query = request.args.get('q')
    posts = []

    if query:
        posts = Post.query.filter(Post.title.contains(query) | Post.content.contains(query)).all()
        return render_template('home.html', posts=posts, query=query)
    
    posts = Post.query.order_by(Post.date.desc()).all()
    return render_template('home.html', posts=posts)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            flash("Username already exists", "danger")
        else:
            user = User(username=username, password=password)
            db.session.add(user)
            db.session.commit()
            flash("Account created!", "success")
            return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash("Logged in successfully!", "success")
            return redirect(url_for('home'))
        flash("Invalid credentials", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for('home'))

@app.route('/create', methods=['GET', 'POST'])
def create():
    if 'user_id' not in session:
        flash("Please log in to create a post.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image = None
        if 'image' in request.files:
            img_file = request.files['image']
            if img_file and img_file.filename != '':
                filename = secure_filename(img_file.filename)
                img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                img_file.save(img_path)
                image = f'uploads/{filename}'

        post = Post(title=title, content=content, image=image, user_id=session['user_id'])
        db.session.add(post)
        db.session.commit()
        flash("Post created!", "success")
        return redirect(url_for('home'))

    return render_template('create_post.html')

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    is_liked = False
    is_bookmarked = False
    if 'user_id' in session:
        is_liked = Like.query.filter_by(user_id=session['user_id'], post_id=post.id).first() is not None
        is_bookmarked = Bookmark.query.filter_by(user_id=session['user_id'], post_id=post.id).first() is not None

        if request.method == 'POST':
            content = request.form.get('comment')
            if content:
                comment = Comment(content=content, user_id=session['user_id'], post_id=post.id)
                db.session.add(comment)
                db.session.commit()
                flash("Comment added!", "success")
                return redirect(url_for('view_post', post_id=post.id))

    return render_template('view_post.html', post=post, is_liked=is_liked, is_bookmarked=is_bookmarked)

@app.route('/like/<int:post_id>')
def like(post_id):
    if 'user_id' not in session:
        flash("Please log in to like posts.", "warning")
        return redirect(url_for('login'))

    like = Like.query.filter_by(user_id=session['user_id'], post_id=post_id).first()
    if like:
        db.session.delete(like)
        flash("Post unliked.", "info")
    else:
        new_like = Like(user_id=session['user_id'], post_id=post_id)
        db.session.add(new_like)
        flash("Post liked!", "success")
    db.session.commit()
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/bookmark/<int:post_id>')
def bookmark(post_id):
    if 'user_id' not in session:
        flash("Please log in to bookmark posts.", "warning")
        return redirect(url_for('login'))

    bm = Bookmark.query.filter_by(user_id=session['user_id'], post_id=post_id).first()
    if bm:
        db.session.delete(bm)
        flash("Bookmark removed.", "info")
    else:
        new_bm = Bookmark(user_id=session['user_id'], post_id=post_id)
        db.session.add(new_bm)
        flash("Post bookmarked!", "success")
    db.session.commit()
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/bookmarks')
def bookmarks():
    if 'user_id' not in session:
        flash("Please log in to view bookmarks.", "warning")
        return redirect(url_for('login'))
    bookmarks = Bookmark.query.filter_by(user_id=session['user_id']).all()
    posts = [bookmark.post for bookmark in bookmarks]
    return render_template('bookmarks.html', posts=posts)

@app.route('/likes')
def likes():
    if 'user_id' not in session:
        flash("Please log in to view liked posts.", "warning")
        return redirect(url_for('login'))
    likes = Like.query.filter_by(user_id=session['user_id']).all()
    posts = [like.post for like in likes]
    return render_template('likes.html', posts=posts)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)

    if 'user_id' not in session or session['user_id'] != post.user_id:
        flash("You don't have permission to edit this post.", "danger")
        return redirect(url_for('view_post', post_id=post.id))

    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        db.session.commit()
        flash("Post updated!", "success")
        return redirect(url_for('view_post', post_id=post.id))

    return render_template('edit_post.html', post=post)

@app.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    if 'user_id' not in session or session['user_id'] != post.user_id:
        flash("You don't have permission to delete this post.", "danger")
        return redirect(url_for('view_post', post_id=post.id))

    db.session.delete(post)
    db.session.commit()
    flash("Post deleted.", "info")
    return redirect(url_for('home'))

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    post_id = comment.post.id

    if 'user_id' not in session or (session['user_id'] != comment.user_id and session['user_id'] != comment.post.user_id):
        flash("You don't have permission to delete this comment.", "danger")
        return redirect(url_for('view_post', post_id=post_id))

    db.session.delete(comment)
    db.session.commit()
    flash("Comment deleted.", "info")
    return redirect(url_for('view_post', post_id=post_id))

# You can add other routes here...

if __name__ == "__main__":
    app.run(debug=True)