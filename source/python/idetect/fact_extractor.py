'''Method(s) for extracting facts from relevant content.

How to ensure has access to pre-loaded models?
'''
import json

import spacy
from itertools import groupby
from sqlalchemy.orm import object_session

from idetect.geotagger import get_geo_info
from idetect.interpreter import Interpreter
from idetect.model import Fact, Location, Country

nlp = spacy.load("en_default")
print("Loaded Spacy English Language NLP Models.")


def extract_facts(analysis):
    '''Extract facts (facts) for given instance of Analysis
    :params article: instance of Analysis
    :return: None
    '''
    session = object_session(analysis)
    interpreter = Interpreter(session, nlp)
    content = analysis.content.content
    facts = interpreter.process_article_new(content)
    if len(facts) > 0:
        save_facts(analysis, facts, session)


def save_facts(analysis, facts, session):
    '''Loop through extracted facts and save them to database
    :params article: instance of Article
    :params facts: list of extracted facts
    :params session: session object corresponding to the article
    :return: None
    '''
    for f in facts:
        # First geolocate locations; split into countries and create one fact per country
        country_locations = []
        for location in f.locations:
            country_locations.extend((process_location(location, session)))

        country_locations.sort(key=lambda x: x.country.iso3)
        for key, group in groupby(country_locations, lambda x: x.country.iso3):

            fact = Fact(unit=f.reporting_unit, term=f.reporting_term,
                    excerpt_start=f.sentence_start, excerpt_end=f.sentence_end,
                    specific_reported_figure=f.quantity[0],
                    vague_reported_figure=f.quantity[1], iso3=key,
                    tag_locations=json.dumps(f.tag_spans))
            session.add(fact)
            session.commit()
            analysis.facts.append(fact)
            fact.locations.extend([location for location in group])


def process_location(location_name, session):
    '''Get geo info for a given location and add the location to database
    :params fact: instance of Fact
    :params location: location name, a String
    :params session: session object corresponding to location
    :return: None
    '''
    locations = []
    location = session.query(Location).filter_by(
        location_name=location_name).one_or_none()
    if location:
        locations.append(location)
    else:
        loc_info = get_geo_info(location_name)
        if loc_info['flag'] != 'no-results':
            country = session.query(Country).filter_by(
                iso3=loc_info['country_code']).one_or_none()
            location = Location(location_name=loc_info['place_name'], location_type=loc_info['type'],
                                country_iso3=country.iso3,
                                country=country, latlong=loc_info['coordinates'])
            session.add(location)
            session.commit()
            locations.append(location)
    return locations
