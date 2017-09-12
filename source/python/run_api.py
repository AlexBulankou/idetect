import logging

from flask import Flask, render_template, abort, request, redirect, url_for
from sqlalchemy import create_engine, desc

from idetect.model import db_url, Base, Analysis, Session, Status, Document, DocumentType

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = Flask(__name__,
            static_folder="/home/idetect/web/static",
            template_folder="/home/idetect/web/templates")

engine = create_engine(db_url())
Session.configure(bind=engine)
Base.metadata.create_all(engine)


@app.route('/')
def homepage():
    session = Session()
    articles = session.query(Analysis).order_by(desc(Analysis.updated)).limit(10).all()
    counts = Analysis.status_counts(session)
    return render_template('index.html', articles=articles, counts=counts)


@app.route('/add_url', methods=['POST'])
def add_url():
    url = request.form['url']
    logger.info("Scraping by url: {url}".format(url=url))
    if url is None:
        return redirect(url_for('/'))
    article = Document(url=url, name="New Document", type=DocumentType.WEB)
    session = Session()
    session.add(article)
    session.commit()
    return render_template('success.html', endpoint='add_url', article=article)

@app.route('/article/<int:doc_id>', methods=['GET'])
def article(doc_id):
    session = Session()
    analysis = session.query(Analysis) \
            .filter(Analysis.document_id == doc_id).one()
    coords = [l.latlong.split(",")[::-1] for f in analysis.facts for l in f.locations]
    return render_template('article.html', article=analysis, coords=coords)


@app.context_processor
def utility_processor():
    def format_date(dt):
        return dt.strftime("%Y-%m-%d %H:%M")

    return dict(format_date=format_date)

if __name__ == "__main__":
    # Start flask app
    app.run(host='0.0.0.0', port=5001, debug=True, threaded=True)
