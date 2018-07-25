import functools
from flask import jsonify, url_for, request, make_response
#from .errors import bad_request
import flask_sqlalchemy
import hashlib

def json(f):
    '''
        This decorator generates a JSON response from a Python dictionary or a SQLAlchemy model

        Add developer/researcher status?
    '''
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        rv = f(*args, **kwargs)

        status  = None
        headers = None

        if isinstance(rv, tuple):
            rv, status, headers = rv + (None,) * (3 - len(rv))

        if isinstance(status, (dict, list)):
            headers, status = status, None

        if not isinstance(rv, dict):
            rv = rv.to_json()

        rv = jsonify(rv)

        if status is not None:
            rv.status_code = status

        if headers is not None:
            rv.headers.extend(headers)

        return rv
    return wrapped

# Documentatino is here: https://github.com/miguelgrinberg/api-pycon2015
def _filter_query(model, query, filter_spec):
    filters = [f.split(',') for f in filter_spec.split(';')]
    for f in filters:
        if len(f) < 3 or (len(f) > 3 and f[1] != 'in'):
            continue
        if f[1] == 'in':
            f = [f[0], f[1], f[2:]]

        ops = {'eq': '__eq__', 'ne': '__ne__', 'lt': '__lt__', 'le': '__le__',
               'gt': '__gt__', 'ge': '__ge__', 'in': 'in_', 'like': 'like'}

        if hasattr(model, f[0]) and f[1] in ops.keys():
            column = getattr(model, f[0])
            op = ops[f[1]]
            query = query.filter(getattr(column, op)(f[2]))

    return query

def _sort_query(model, query, sort_spec):
    '''  '''
    sort = [s.split(',') for s in sort_spec.split(';')]
    for s in sort:
        if hasattr(model, s[0]):
            column = getattr(model, s[0])
            if len(s) == 2 and s[1] in ['asc', 'desc']:
                query = query.order_by(getattr(column, s[1])())
            else:
                query = query.order_by(column.asc())

    return query

def _collection(model, query, id=None, name=None, default_per_page=50,
                max_per_page=10000, researcher=False, **kwargs):
    '''
        This function should act nearly the same as the aptly named decorator,
        but doesn't require knowledge of the model before hand
    '''
    if name is None:
        name = model.__tablename__

    filter = request.args.get('filter')
    if filter:
        query = _filter_query(model, query, filter)

    sort = request.args.get('sort')
    if sort:
        query = _sort_query(model, query, sort)

    limit = request.args.get('limit')
    if limit:
        query = query.limit(limit)

    # Pagination
    page = request.args.get('page', 1, type = int)
    per_page = min(request.args.get('per_page', default_per_page, type=int), max_per_page)
    expand = request.args.get('expand', 1)

    p = query.paginate(page, per_page)
    pages = {'page': page, 'per_page': per_page, 'total': p.total, 'pages': p.pages}

    if p.has_prev:
        pages['prev_url'] = url_for(request.endpoint, id=id, page=p.prev_num,
                            per_page=per_page, expand=expand, _external=True, _scheme='https', **kwargs)
    else:
        pages['prev_page'] = None

    if p.has_next:
        pages['next_url'] = url_for(request.endpoint, id=id, page=p.next_num,
                            per_page=per_page, expand=expand, _external=True, _scheme='https', **kwargs)
    else:
        pages['next_page'] = None

    pages['first_url'] = url_for(request.endpoint, id=id, filter=filter, sort=sort, page = 1,
                            per_page=per_page, expand=expand, _external=True, _scheme='https', **kwargs)

    pages['last_url'] = url_for(request.endpoint, id=id, filter=filter, sort=sort, page=p.pages,
                            per_page=per_page, expand=expand, _external=True, _scheme='https', **kwargs)

    if expand:
        items = [item.to_json(researcher=researcher) for item in p.items]
    else:
        items = [item.get_url() for item in p.items]

    return {'data': items, 'meta': pages}

def collection(model, name=None, default_per_page=50, max_per_page=10000):
    '''
        This decorator implements pagination, filtering, sorting, and expanding
        for collections. The expected response from the decorated route is a
        SQLAlchemy query
    '''
    if name is None:
        name = model.__tablename__

    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            query = f(*args, **kwargs)

            # here, we need to return an actual error! not sure why the other method wasn't raised
            # THIS IS A STUPID HACK GET RID OF ME
            if not isinstance(query, flask_sqlalchemy.BaseQuery):
                return {'meta': {}, 'data': []}

            # Filtering and Sorting
            filter = request.args.get('filter')
            if filter:
                query = _filter_query(model, query, filter)

            sort = request.args.get('sort')
            if sort:
                query = _sort_query(model, query, sort)

            #limit = request.args.get('limit')
            #if limit:
            #    query = query.limit(limit)

            # Pagination
            page = request.args.get('page', 1, type=int)
            per_page = min(request.args.get('per_page', default_per_page, type=int),
                            max_per_page)
            expand = request.args.get('expand', 1)


            p = query.paginate(page, per_page)
            pages = {'page': page, 'per_page': per_page, 'total': p.total, 'pages': p.pages}

            if p.has_prev:
                pages['prev_url'] = url_for(request.endpoint, page=p.prev_num,
                                    per_page=per_page, expand=expand,
                                    _external=True, _scheme='https', **kwargs)
            else:
                pages['prev_page'] = None

            if p.has_next:
                pages['next_url'] = url_for(request.endpoint, page=p.next_num,
                                    per_page=per_page, expand=expand,
                                    _external=True, _scheme='https', **kwargs)
            else:
                pages['next_page'] = None

            pages['first_url'] = url_for(request.endpoint, filter=filter, sort=sort, page=1,
                                    per_page=per_page, expand=expand, _external=True, _scheme='https', **kwargs)

            pages['last_url'] = url_for(request.endpoint, filter=filter, sort=sort, page=p.pages,
                                    per_page=per_page, expand=expand, _external=True, _scheme='https', **kwargs)

            if expand:
                items = [item.to_json() for item in p.items]
            else:
                items = [item.get_url() for item in p.items]

            return {'data': items, 'meta': pages}
        return wrapped
    return decorator

def cache_control(*directives):
    ''' Insert a Cache-control header with the given directives '''
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            # Invoke the function and return the route
            rv = f(*args, **kwargs)

            # conver tthe returned value to a response object
            rv = make_response(rv)

            # Insert the Cache-Control header and return response
            rv.headers['Cache-Control'] = ', '.join(directives)
            return rv
        return wrapped
    return decorator

def no_cache(f):
    ''' Insert a no-cache directive in the response '''
    return cache_control('private', 'no-cache', 'no-store', 'max-age=0')(f)

def etag(f):
    ''' Add entity tag (etag) handling to the decorated route '''
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if request.method not in ['GET', 'HEAD']:
            return make_response(f(*args, **kwargs))

        rv = f(*args, **kwargs)
        rv = make_response(rv)

        if rv.status_code != 200:
            return rv

        etag = '"' + hashlib.md5(rv.get_data()).hexdigest() + '"'
        rv.headers['ETag'] = etag

        # Handle if-match and if-none-match request headers
        if_match = request.headers.get('If-Match')
        if_none_match = request.headers.get('If-None-Match')
        if if_match:
            etag_list = [tag.strip() for tag in if_match.split(',')]
            if etag not in etag_list and '*' not in etag_list:
                response = jsonify({'status': 412, 'error': 'precondition failed',
                            'message': 'precondition failed'})
                response.status_code = 412
                return response
        elif if_none_match:
            etag_list = [tag.strip() for tag in if_none_match.split(',')]
            if etag in etag_list or '*' in etag_list:
                response = jsonify({'status': 304, 'error': 'not modified',
                                'message': 'resource not modified'})
                response.status_code = 304
                return response
        return rv
    return wrapped
