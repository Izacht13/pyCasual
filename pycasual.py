import re


##############################
#/                          \#
#|      Debug Options       |#
#\                          /#
##############################

# Flatten nested arrays in tags and content
ALLOW_TAG_FLATTENING = True


##############################
#/                          \#
#|      Tag Functions       |#
#\                          /#
##############################

def __tagfunc_append__(element, args):
	while args and element.content:
		element.child(args.pop(), element.content.pop())


def __tagfunc_riter__(element, args):
	if not (element.parent and args):
		return
	for child in element:
		l = len(child.content)
		attributes = [Attribute(args[0], child.tag)]
		for i, tag in enumerate(args[1:]):
			attributes.append(Attribute(tag, child.content[
							  i] if i < l and child.content != ' ' else None))
		element.parent.add_child(element.tag, attributes=attributes)
	element.parent.children.remove(element)

TAG_FUNCTIONS = {
	"#": "id",
	".": "class",
	"<": __tagfunc_riter__,
	"&": __tagfunc_append__
}


##############################
#/                          \#
#|       Tree Objects       |#
#\                          /#
##############################

class Tag(list):

	def serialize(self):
		return ''.join([''.join(t) if isinstance(t, list) and ALLOW_TAG_FLATTENING else str(t) for t in self])


class Content(Tag):
	pass


class TaggedContent(object):

	def __init__(self, tag=None, content=None):
		self.tag = Tag(tag or [])
		self.content = Content(content or [])

	def __eq__(self, x):
		if isinstance(x, TaggedContent):
			return self.tag == x.tag
		return self.tag == x

	def __str__(self):
		return self.serialize()

	def serialize(self):
		return "<{tag}>{content}</{tag}>".format(
			tag=self.tag.serialize().strip() or "div",
			content=self.content.serialize()
		)


class Attribute(TaggedContent):

	def serialize(self):
		return self.tag.serialize() + ("=\"%s\"" % self.content.serialize() if self.content else '')


class Element(TaggedContent):

	def __init__(self, tag=None, parent=None, content=None, attributes=None, children=None):
		super().__init__(tag, content)
		self.children = children or []
		self.attributes = attributes or []

		if parent and isinstance(parent, Element):
			self.parent = parent
		else:
			self.parent = None

	def __getitem__(self, key):
		for child in self.children:
			if child == key:
				return child
		raise KeyError

	def __setitem__(self, key, value):
		child = self.__getitem__(key)
		child = value

	def get_child(self, tag):
		for child in self.children:
			if child == tag:
				return child
		return None

	def get_attribute(self, tag):
		for child in self.children:
			if child == tag:
				return child
		return None

	def add_child(self, tag, content=None, attributes=None, children=None):
		self.children.append(Element(tag, self, content, attributes, children))
		return self.children[-1]

	def add_attribute(self, tag, content=None):
		self.attributes.append(Attribute(tag, content))
		return self.attributes[-1]

	def add(self, item):
		if isinstance(item, Element):
			item.parent = self
			self.children.append(item)
			return self.children[-1]
		elif isinstance(item, Attribute):
			self.attributes.append(item)
			return self.attributes[-1]
		return None

	def __iter__(self):
		yield from self.children

	def __str__(self):
		return self.serialize()

	def serialize(self):
		tag = self.tag.serialize().strip()
		single = False
		if tag and tag[-1] == '/':
			single = True
			tag = tag[:-1]
		return ("<{tag} {attributes}>" + ("{content}{children}</{tag}>" if not single else '')).format(
			tag=tag or "div",
			content=self.content.serialize(),
			attributes=''.join([a.serialize() for a in self.attributes]),
			children=''.join([c.serialize() for c in self.children]),
		)

	def transform(self, functions=TAG_FUNCTIONS):
		e = 0
		for i, t in enumerate(self.tag):
			if t in functions:
				function = functions[t]
				args = [a for a in self.tag[i + 1:] if a != ' ']
				self.tag = Tag(self.tag[:i])
				if callable(function):
					function(self, args)
				elif isinstance(function, str):
					if function[0] == ':':
						self.add_child(function[1:], args)
					else:
						self.add_attribute(function, args)
				# elif isinstance(function[t], re._pattern_type):
				# 	for child in self.children:
				# 		if function[t].search(''.join(child.tag))
				e += 1
				break
		for child in reversed(self.children):
			e += child.transform(functions)
		return e


class Root(Element):

	def serialize(self):
		return ''.join([c.serialize() for c in self.children])


##############################
#/                          \#
#|     CasualML Parser      |#
#\                          /#
##############################

class Parser(object):

	class Context(list):

		def push(self, depth, anchor=None):
			self.append((depth, anchor))

		def isattribute(self, index=None):
			if isinstance(self[index or -1][1], Attribute):
				return True
			return False

		def iselement(self, index=None):
			if isinstance(self[index or -1][1], Element):
				return True
			return False

		def isroot(self, index=None):
			if isinstance(self[index or -1][1], Root):
				return True
			return False

		def __getattr__(self, name):
			if name == "top":
				return self[-1][1]
			super().__getattr__(name)

		def __setattr__(self, name, value):
			if name == "top":
				self[-1] = (self[-1][0], value)
			else:
				super().__setattr__(name, value)

	class Tokens:
		UNKNOWN = 0
		COMMENT = 1
		RAWSTRING = 2
		STRING = 3
		ESCAPE = 4
		BRACKET = 5
		ENDBRACKET = 6
		LINEBREAK = 7
		BREAK = 8
		TAG = 9
		SPACE = 10
		TEXT = 11
		SYMBOL = 12

	__lexemes__ = [(re.compile(x[1]), x[0]) for x in [
		(Tokens.COMMENT, r"\/{2,}\s*(([^\/\n\r])*)(\/{2,})*"),
		(Tokens.RAWSTRING, r"\"(([^\"\\]|\\.)*)\""),
		(Tokens.STRING, r"'(([^'\\\n\r]|\\.)*)'"),
		(Tokens.ESCAPE, r"\\(.)"),
		(Tokens.BRACKET, r"([\[\{])"),
		(Tokens.ENDBRACKET, r"([\]\}])"),
		(Tokens.LINEBREAK, r"([\n\r]+)"),
		(Tokens.BREAK, r"([,;])[ \t\f\v,;]*"),
		(Tokens.TAG, r"([:=])[ \t\f\v]*"),
		(Tokens.SPACE, r"([ \t\f\v])"),
		(Tokens.TEXT, r"(\w+)"),
		(Tokens.SYMBOL, r"([\!\@\#\$\%\^\&\*\?\/\.\+\-\|\~\(\)\`<>])"),
		(Tokens.UNKNOWN, r"(.)")
	]]

	def __init__(self, script=None):
		self.script = script

	def tokens(self, script=None):
		"""Returns a generator of tokens matched in the script."""
		self.script = script or self.script
		if not self.script:
			return

		index = 0
		scrlen = len(self.script)

		while True:
			for lexeme in Parser.__lexemes__:
				match = lexeme[0].match(self.script[index:])
				if match:
					yield (lexeme[1], match.group(1))
					index += match.span()[1] - 1
					break

			if index < scrlen:
				index += 1
			else:
				break

	def parse(self, script=None, transform=True, *, tokens=None):
		"""Set transform to False to disable tag functions."""
		self.script = (script or self.script) + ';'
		if not self.script:
			return

		tokens = tokens or self.tokens()
		if not tokens:
			return
		token = next(tokens, None)

		root = Root()
		buffer = []
		depth = 0
		depth_test = True
		indent = False
		attribute_bracket = False
		list_bracket = False
		last_bracket = None

		context = Parser.Context()
		context.push(-1, root)

		while token:
			if depth_test:
				if token[0] == Parser.Tokens.SPACE:
					depth += 1
				else:
					depth_test = False
					if not list_bracket:
						while depth < context[-1][0]:
							context.pop()
						if depth > context[-1][0]:
							indent = True
					continue
			else:
				if token[0] == Parser.Tokens.LINEBREAK:
					if list_bracket:
						# This below re-tests for something we already knew...
						# If the last token was a break or not, but because we already
						# threw away that data, so we have to re-test.
						# The only way I can think to fix this right now, is to
						# include the whole token in the buffer.
						if buffer and buffer[-1] not in ";,":
							buffer.append(last_bracket)
					elif buffer:
						context.top.content.append(buffer)
						buffer = []
					depth = 0
					depth_test = True
					indent = False
				elif token[0] == Parser.Tokens.BREAK:
					if list_bracket:
						buffer.append(token[1])
						last_bracket = token[1]
					else:
						if buffer:
							context.top.content.append(buffer)
							buffer = []
						if token[1] == ',' and attribute_bracket:
							if context.iselement():
								context.top.attribute(buffer)
								buffer = []
				elif token[0] == Parser.Tokens.BRACKET:
					if buffer:
						context.top.content.append(buffer)
						buffer = []
					if token[1] == '[' and not (attribute_bracket or list_bracket):
						attribute_bracket = True
					elif token[1] == '{' and not list_bracket:
						list_bracket = True
					else:
						buffer.append(token[1])
				elif token[0] == Parser.Tokens.ENDBRACKET:
					if token[1] == ']' and attribute_bracket:
						if buffer and context.iselement():
							context.top.add_attribute(buffer)
							buffer = []
						attribute_bracket = False
					elif token[1] == '}' and list_bracket:
						if buffer:
							context.top.content.append(buffer)
							buffer = []
						list_bracket = False
						last_bracket = None
					else:
						buffer.append(token[1])
				elif token[0] == Parser.Tokens.TAG:
					if list_bracket:
						buffer.append(token[1])
					else:
						if token[1] == ':' and not attribute_bracket:
							new = Element(buffer)
						elif token[1] == '=':
							new = Attribute(buffer)
						else:
							new = None
							buffer.append(token[1])
						if new:
							if indent and context.iselement():
								context.top.add(new)
								context.push(depth, new)
							elif not indent and context.iselement(-2):
								context[-2][1].add(new)
								context.top = new
							buffer = []
				elif token[0] == Parser.Tokens.COMMENT:
					pass
				elif token[0] == Parser.Tokens.UNKNOWN:
					pass
				else:
					buffer.append(token[1])

			token = next(tokens, None)

		if transform:
			root.transform()
		return root


def parse(script=None, transform=True):
	"""Set transform to False to disable tag functions."""
	return Parser(script).parse()
