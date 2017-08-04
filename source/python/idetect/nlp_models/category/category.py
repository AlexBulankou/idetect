import gensim
import pandas as pd
import numpy as np
from nltk.tokenize import WordPunctTokenizer
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.externals import joblib

from idetect.model import Category
from idetect.nlp_models.base_model import DownloadableModel


class CategoryModel(DownloadableModel):

    def predict(self, text):
        try:
            category = self.model.predict(pd.Series(text))[0]
            if category == 'disaster':
                return Category.DISASTER
            elif category == 'conflict':
                return Category.CONFLICT
            else:
                return Category.OTHER
        except ValueError:
            # error can occur if empty text is passed to model
            raise


class Tokenizer(TransformerMixin):
    def __init__(self, stop_words=None):
        self.stop_words = stop_words
        self.tokenizer = WordPunctTokenizer()

    def prepare_tokens(self, text, stop_words):
        tokens = self.tokenizer.tokenize(text)
        tokens = [t for t in tokens if len(t) > 2]
        tokens = [t for t in tokens if t not in stop_words]
        tokens = [t.lower() for t in tokens]
        tokens = [t for t in tokens if not t.isdigit()]
        return tokens

    def fit(self, X, *args):
        return self

    def transform(self, X, *args):
        X = X.map(lambda x: self.prepare_tokens(x, self.stop_words))
        return X


class TfidfTransformer(TransformerMixin):
    def __init__(self, no_below=5, no_above=0.5):
        self.no_below = no_below
        self.no_above = no_above

    def set_dictionary(self, texts):
        self.dictionary = gensim.corpora.Dictionary(texts)
        if self.no_below or self.no_above:
            self.dictionary.filter_extremes(no_below=self.no_below,
                                            no_above=self.no_above)

    def make_corpus(self, texts):
        corpus = [self.dictionary.doc2bow(text) for text in texts]
        return corpus

    def set_tfidf_model(self, corpus):
        self.tfidf_model = gensim.models.TfidfModel(corpus)

    def fit(self, texts, y=None):
        self.set_dictionary(texts)
        corpus = self.make_corpus(texts)
        self.set_tfidf_model(corpus)
        return self

    def transform(self, texts):
        corpus = self.make_corpus(texts)
        return self.tfidf_model[corpus]


class LsiTransformer(TransformerMixin):
    def __init__(self, n_dimensions=100, no_below=5, no_above=0.5):
        self.n_dimensions = n_dimensions
        self.no_below = no_below
        self.no_above = no_above

    def lsi_to_vecs(self, corpus_lsi):
        lsi_vecs = []
        for c in corpus_lsi:
            vec = [x[1] for x in c]
            lsi_vecs.append(vec)
        return np.array(lsi_vecs)

    def make_tfidf(self, texts):
        self.tfidf_transformer = TfidfTransformer(no_below=self.no_below,
                                                  no_above=self.no_above)
        self.tfidf_transformer.fit(texts)
        corpus_tfidf = self.tfidf_transformer.transform(texts)
        dictionary = self.tfidf_transformer.dictionary
        return corpus_tfidf, dictionary

    def make_corpus(self, corpus_tfidf):
        lsi_corpus = self.lsi_model[corpus_tfidf]
        return lsi_corpus

    def set_lsi_model(self, texts):
        corpus_tfidf, dictionary = self.make_tfidf(texts)
        self.lsi_model = gensim.models.LsiModel(corpus_tfidf,
                                            id2word=dictionary,
                                            num_topics=self.n_dimensions)

    def fit(self, texts, *args, **kwargs):
        self.set_lsi_model(texts)
        self.corpus_lsi = self.lsi_model[self.corpus_tfidf]
        return self

    def transform(self, texts):
        corpus_tfidf, _dictionary = self.make_tfidf(texts)
        corpus_lsi = self.make_corpus(corpus_tfidf)
        return self.lsi_to_vecs(corpus_lsi)