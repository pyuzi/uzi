import re
import sys
import base64
from functools import lru_cache



def begin(text, begin, n=1):
	"""
	Start a string with only n instances of a given value.
	"""
	text = re.sub('^'+re.escape(begin)+'+', '', text)
	return (begin*n)+text


def compact(text, *, strip=True, space=' '):
	"""
	Remove all repeating spaces and replace space with a single instance of
	the given (space) value.
	If strip is True, the string will also be striped.
	"""
	if strip and space:
		text = text.strip()
	return re.sub(r'\s+', space, text)


def concat(iterable, sep = ' ', minified = False):
	text = sep.join(iterable)
	return minified(text, sep) if minified else compact(text)


def humanize(value):
	if not value:
		return str(value)
	text = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', str(value))
	text = re.sub('([a-z0-9.])([A-Z])', r'\1 \2', text)
	text = re.sub('(\.)([^\s.])', r'\1 \2', text)
	return re.sub(r'_+', ' ', text)


def finish(text, finish, n=1):
	"""
	End a string with n instances of a given value.
	"""
	text = re.sub(re.escape(finish)+'+$', '', text)
	return text+(finish*n)


def matches(pattern, text):
	"""Determine if a given string matches a given pattern."""
	pattern = re.escape(pattern).replace('\*', '.*')
	if re.match(pattern, text):
		return True
	else:
		return False


def minify(text, replace=' '):
	text = re.sub('[\t\n\r\f\v]+', replace, text)
	return compact(text)



def replace(text, search, replace = ''):
	if isinstance(search, dict):
		items = dict((re.escape(k), search[k]) for k in search.keys())
	elif isinstance(search, str):
		if not isinstance(replace, str):
			m = "The replacement value for strings ({0}) should also be string. {1} given."
			raise ValueError(m.format(search, type(replace).title()))
		items = {re.escape(search) : replace}
	else:
		if isinstance(replace, str):
			items = dict((re.escape(s), replace) for s in search)
		else:
			items = dict((re.escape(s), r) for s, r in zip(search, replace))

	pattern = re.compile("|".join(items.keys()))
	return pattern.sub(lambda m: items[re.escape(m.group(0))], text)


def slice(text, length=100, offset = 0, last_word=True):
	"""
	Slice a string.
	"""
	text = text[offset:]
	if len(text) <= length or not last_word:
		return text[:length]
	return re.sub('(\s+\S+\s*)$', '', text[:length])


def truncate(text, length=100, offset=0, words=False):
	"""Truncate a string."""
	return slice(text, length=length, offset=offset, last_word=words)


@lru_cache(1024)
def slug_re(sep: str='-', allow: str = '', pathlike=False, space=False, allow_re: str= '', flags: int = 0) -> re.Pattern:
	esep = re.escape(sep or '-')
	allow = pathlike and f'{allow or ""}:/.+' or allow or ''
	eallow = allow and re.escape(allow)
	space = space and r'\s' or ''
	return re.compile(f'[^{eallow}{esep}{allow_re or ""}0-9a-zA-Z{space}_-]+', flags)


@lru_cache(128)
def slug_space_re(sep: str='-', allow: str = '', allow_re: str= '', flags: int = 0):
	esep = re.escape(sep or '-')
	eallow = allow and re.escape(allow) or ''
	return re.compile(f'[\s{eallow}{esep}{allow_re or ""}]+', flags)


def slug(text, *, sep = '-', allow: str='', pathlike=False):
	if text:
		return slug_space_re(sep)\
			.sub(
				sep,
				slug_re(sep, allow, pathlike, True).sub('', text.lower())
			)
	return ''


def is_slug(text, *, allow: str='', sep: str = '-', pathlike=False) -> bool:
	"""Check if text only consists of slug chars [^{allow}{sep}0-9a-zA-Z_-]+
	"""
	return not slug_re(sep, allow, pathlike).search(text)
	
def snake(text, /, *, sep='_', ignore: str =''):
	sep = sep or '_'
	ignore = re.escape(sep + ignore)
	text = re.sub(f'([^\s{ignore}])' + r'([A-Z][a-z]+)', f'\\1{sep}\\2', text)
	text = re.sub(r'([a-z0-9])([A-Z])', f'\\1{sep}\\2', text).lower()
	return re.sub(f'[^0-9a-z{ignore}]+', sep, text)


def camel(val: str) -> str:
	rv = uppercamel(val)
	return rv[0].lower() + rv[1:]



def uppercamel(val: str) -> str:
	return startcase(val).replace(' ', '')


def startcase(val) -> str:
	return compact(snake(val, sep=' ')).title()


def words(text, words=100, end ='...'):
	pattern = re.compile('(\s*\S+\s*){1,'+str(words)+'}')
	matches = pattern.match(text)

	if not matches:
		return text

	short = matches.group(0)
	if len(text) > len(short):
		return short.rstrip() + end
	else:
		return short


def to_bytes(x, charset=sys.getdefaultencoding(), errors='strict'):
	if x is None:
		return None
	if isinstance(x, (bytes, bytearray, memoryview)):
		return bytes(x)
	if isinstance(x, str):
		return x.encode(charset, errors)
	raise TypeError('Expected bytes')


def is_hex(s):
	return re.fullmatch(r"^[0-9a-fA-F]+$", s or "") is not None


def tobase64(s, padding=None, altchars=b'-_'):
	rv = base64.b64encode(to_bytes(s), altchars).decode()
	if padding is int:
		lenb4, rv = len(rv), rv.rstrip('=')
		rv = '%s%s' % (rv, str(lenb4-len(rv)))
	elif padding:
		rv = rv.replace('=', padding)
	return rv


def debase64(s, padding=None, altchars=b'-_', validate=False):
	if padding is int:
		pad, s = int(s[-1]), s[:-1]
		s = '%s%s' % (s, '='*pad)
	elif padding:
		pattern = '^(.*)[%s]+$' % re.escape(padding)
		s = re.sub(pattern, r'\1\=')
	rv = base64.b64decode(s, altchars=altchars, validate=validate)
	return rv.decode()



def is_dunder(val: str) -> bool:
    """Returns True if a __dunder__ name, False otherwise."""
    return (len(val) > 4 and
            val[:2] == val[-2:] == '__' and
            val[2] != '_' and
            val[-3] != '_')



def is_sunder(val: str) -> bool:
    """Returns True if a _sunder_ name, False otherwise."""
    return (len(val) > 2 and
            val[0] == val[-1] == '_' and
            val[1:2] != '_' and
            val[-2:-1] != '_')
