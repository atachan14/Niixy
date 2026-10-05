"""AccountLayout language: inert HTML + a deliberately small CSS grammar.

Never pass source to Django's template engine. Rebuild HTML, validate CSS tokens,
then render inside a host-controlled Shadow DOM. Preview and Profile use this path.
"""
import re
import uuid
from html import escape, unescape
from html.parser import HTMLParser

import tinycss2
from tinycss2.color3 import parse_color
from django.core.exceptions import ValidationError

TAGS = {'div', 'section', 'article', 'header', 'footer', 'main', 'span', 'p',
        'h1', 'h2', 'h3', 'h4', 'strong', 'em', 'small', 'b', 'i', 'ul', 'ol',
        'li', 'dl', 'dt', 'dd', 'br', 'hr'}
VOID = {'br', 'hr'}
ALIAS = re.compile(r'[A-Za-z][A-Za-z0-9_]{0,31}\Z')
CLASS = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,47}\Z')
BINDING = re.compile(r'\{\{\s*([A-Za-z][A-Za-z0-9_]*)\.(name|value)\s*\}\}')


def fail(message):
    raise ValidationError(message)


def text_binding(text, items, *, values=None):
    out, end = [], 0
    for match in BINDING.finditer(text):
        literal = text[end:match.start()]
        if any(s in literal for s in ('{{', '}}', '{%', '%}')):
            fail('HTMLの変数は {{変数名.name}} / {{変数名.value}} で書いてください。')
        alias, part = match.groups()
        if alias not in items:
            fail(f'変数「{alias}」のItemがありません。RequireからItemを追加してください。')
        out.append(escape(literal))
        out.append(escape(str(values[alias][part])) if values is not None else match.group())
        end = match.end()
    literal = text[end:]
    if any(s in literal for s in ('{{', '}}', '{%', '%}')):
        fail('HTMLの変数は {{変数名.name}} / {{変数名.value}} で書いてください。')
    out.append(escape(literal))
    return ''.join(out)


class LayoutHTML(HTMLParser):
    def __init__(self, items, values=None):
        super().__init__(convert_charrefs=False)
        self.items, self.values = items, values
        self.output, self.stack = [], []
        self.nodes = 0

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if tag not in TAGS:
            fail(f'HTML要素 <{tag}> は使用できません。')
        if self.nodes > 300 or len(self.stack) >= 20:
            fail('HTMLは300要素・入れ子20段以内で書いてください。')
        seen, safe = set(), []
        for name, value in attrs:
            if name in seen or name not in {'class', 'title', 'lang', 'aria-label'} or value is None:
                fail(f'HTML属性「{name}」は使用できません。class/title/lang/aria-labelを使えます。')
            seen.add(name)
            if len(value) > 240 or any(s in value for s in ('{{', '}}', '{%', '%}')):
                fail('HTML属性には変数を使えません。属性は240文字以内で書いてください。')
            if name == 'class' and (not value.split() or any(not CLASS.fullmatch(c) for c in value.split())):
                fail('classは英字から始まる英数字・ハイフン・アンダースコアで書いてください。')
            safe.append(f' {name}="{escape(value, quote=True)}"')
        self.output.append(f'<{tag}{"".join(safe)}>')
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag not in VOID:
            fail('自己終了タグはbr/hrだけに使えます。')
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            fail(f'HTMLの閉じタグ </{tag}> の対応を確認してください。')
        self.stack.pop()
        self.output.append(f'</{tag}>')

    def handle_data(self, data):
        if '<' in data:
            fail('HTMLのタグ構文を確認してください。文字としての < は &lt; と書いてください。')
        self.output.append(text_binding(data, self.items, values=self.values))

    def handle_entityref(self, name):
        self.output.append(escape(unescape('&' + name + ';')))

    def handle_charref(self, name):
        self.output.append(escape(unescape('&#' + name + ';')))

    def handle_comment(self, data):
        fail('HTMLコメントは使用できません。')

    def handle_decl(self, decl):
        fail('DOCTYPEは使用できません。HTML本文だけを書いてください。')

    def handle_pi(self, data):
        fail('HTMLの処理命令は使用できません。')

    def unknown_decl(self, data):
        fail('HTML宣言は使用できません。')


def html_fragment(source, items, values=None):
    if not isinstance(source, str) or len(source) > 20000 or '\x00' in source:
        fail('HTMLは20,000文字以内で書いてください。')
    parser = LayoutHTML(items, values)
    parser.feed(source)
    parser.close()
    if parser.stack:
        fail(f'HTMLの <{parser.stack[-1]}> を閉じてください。')
    return ''.join(parser.output)


ENUMS = {
    'display': {'block', 'inline', 'inline-block', 'flex', 'inline-flex', 'grid', 'inline-grid'},
    'flex-direction': {'row', 'column', 'row-reverse', 'column-reverse'},
    'flex-wrap': {'wrap', 'nowrap', 'wrap-reverse'},
    'justify-content': {'start', 'end', 'center', 'space-between', 'space-around', 'space-evenly', 'flex-start', 'flex-end'},
    'align-items': {'start', 'end', 'center', 'stretch', 'baseline', 'flex-start', 'flex-end'},
    'align-self': {'auto', 'start', 'end', 'center', 'stretch', 'baseline', 'flex-start', 'flex-end'},
    'text-align': {'left', 'right', 'center', 'start', 'end'},
    'font-style': {'normal', 'italic'}, 'font-weight': {'normal', 'bold', '400', '500', '600', '700'},
    'font-family': {'sans-serif', 'serif', 'monospace'},
    'white-space': {'normal', 'pre-wrap', 'pre-line'},
    'overflow-wrap': {'normal', 'anywhere', 'break-word'},
    'border-style': {'none', 'solid', 'dashed', 'dotted'},
}
LENGTHS = {'width', 'min-width', 'max-width', 'height', 'min-height', 'max-height',
           'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
           'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
           'gap', 'row-gap', 'column-gap', 'border-radius', 'border-width', 'flex-basis', 'font-size', 'line-height'}
COLORS = {'color', 'background-color', 'border-color'}


def meaningful(tokens):
    return [t for t in tokens if t.type != 'whitespace']


def length(token, *, grid=False):
    if token.type == 'number':
        return token.value == 0
    if token.type == 'percentage':
        return 0 <= token.value <= 100
    if token.type == 'dimension':
        limits = {'px': 1200, 'em': 80, 'rem': 80}
        if grid:
            limits['fr'] = 12
        return token.lower_unit in limits and 0 <= token.value <= limits[token.lower_unit]
    return token.type == 'ident' and token.value in {'auto', 'min-content', 'max-content'}


def grid_value(tokens, depth=0):
    if depth > 2 or not tokens:
        return False
    for token in tokens:
        if length(token, grid=True) or token.type == 'ident' and token.value == 'none':
            continue
        if token.type != 'function' or token.lower_name not in {'repeat', 'minmax'}:
            return False
        args = meaningful(token.arguments)
        commas = [i for i, t in enumerate(args) if t.type == 'literal' and t.value == ',']
        if len(commas) != 1:
            return False
        i = commas[0]
        left, right = args[:i], args[i+1:]
        if token.lower_name == 'repeat':
            if len(left) != 1 or not (left[0].type == 'number' and left[0].int_value is not None and 1 <= left[0].value <= 12
                                     or left[0].type == 'ident' and left[0].value in {'auto-fit', 'auto-fill'}):
                return False
        elif len(left) != 1 or not length(left[0], grid=True):
            return False
        if not grid_value(right, depth + 1):
            return False
    return True


def declarations(tokens):
    out = []
    for d in tinycss2.parse_declaration_list(tokens, skip_comments=False, skip_whitespace=True):
        if d.type != 'declaration' or d.important:
            fail('CSS宣言の構文を確認してください。コメント・!important・入れ子宣言は使えません。')
        name, value = d.lower_name, meaningful(d.value)
        serialized = tinycss2.serialize(value)
        valid = False
        if name in ENUMS:
            valid = len(value) == 1 and serialized in ENUMS[name]
        elif name in COLORS:
            valid = len(value) == 1 and parse_color(value[0]) is not None and serialized not in {'inherit', 'currentColor'}
        elif name in LENGTHS:
            valid = 1 <= len(value) <= (4 if name in {'margin', 'padding', 'border-radius', 'border-width'} else 2 if name == 'gap' else 1)
            valid = valid and all(length(t) for t in value)
            keywords = {'auto', 'min-content', 'max-content'} if name in {'width', 'height', 'min-width', 'max-width', 'min-height', 'max-height', 'flex-basis'} else {'auto'} if name.startswith('margin') else set()
            valid = valid and all(t.type != 'ident' or t.value in keywords for t in value)
            if name == 'line-height' and len(value) == 1 and value[0].type == 'number':
                valid = 1 <= value[0].value <= 4
            if name == 'font-size' and len(value) == 1:
                t = value[0]
                valid = t.type == 'dimension' and (t.lower_unit == 'px' and 8 <= t.value <= 72 or t.lower_unit in {'em', 'rem'} and .5 <= t.value <= 5)
        elif name in {'grid-template-columns', 'grid-template-rows'}:
            valid = len(value) <= 24 and grid_value(value)
        elif name in {'flex-grow', 'flex-shrink'}:
            valid = len(value) == 1 and value[0].type == 'number' and 0 <= value[0].value <= 12
        if not valid:
            fail(f'CSS「{name}: {serialized}」は使用できません。許可された値・単位を確認してください。')
        out.append(f'{name}:{tinycss2.serialize(d.value)};')
    return ''.join(out)


def selectors(tokens):
    # Token grammar: tag/class/* compounds, descendant and child combinators,
    # comma lists. No IDs, attributes, pseudo selectors, escaping to parent.
    tokens = [t for t in tokens if t.type != 'whitespace' or t.value]
    expect, compound, out, i = True, False, [], 0
    while i < len(tokens):
        t = tokens[i]
        if t.type == 'whitespace':
            out.append(' ')
            compound = False
        elif t.type == 'ident' and t.value in TAGS and not compound:
            out.append(t.value); expect = False; compound = True
        elif t.type == 'literal' and t.value == '*' and not compound:
            out.append('*'); expect = False; compound = True
        elif t.type == 'literal' and t.value == '.' and i+1 < len(tokens) and tokens[i+1].type == 'ident' and CLASS.fullmatch(tokens[i+1].value):
            out.append('.' + tokens[i+1].value); i += 1; expect = False; compound = True
        elif t.type == 'literal' and t.value in {',', '>'} and not expect:
            out.append(t.value); expect = True; compound = False
        else:
            fail('CSS selectorは要素名・.class・子孫・ > ・カンマ区切りだけを使えます。')
        i += 1
    if expect or not out:
        fail('CSS selectorを確認してください。')
    return ''.join(out)


def stylesheet(source, scope=None):
    if not isinstance(source, str) or len(source) > 10000:
        fail('CSSは10,000文字以内で書いてください。')
    # CSS parsers repair EOF by implicitly closing blocks. This authoring language
    # instead reports malformed source. Strings/comments are outside its grammar,
    # so delimiter validation is unambiguous; the parser still validates all tokens.
    if any(c in source for c in ('"', "'")) or '/*' in source or '\x00' in source:
        fail('CSSの文字列・コメント・制御文字は使用できません。')
    stack = []
    pairs = {'}': '{', ')': '(', ']': '['}
    for char in source:
        if char in '{([':
            stack.append(char)
            if len(stack) > 12:
                fail('CSSの入れ子が深すぎます。')
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                fail('CSSの括弧・波括弧の対応を確認してください。')
    if stack:
        fail('CSSの括弧・波括弧を閉じてください。')
    count = [0]
    def rules(nodes, depth=0):
        if depth > 3:
            fail('CSSの@mediaは入れ子3段以内で書いてください。')
        out = []
        for rule in nodes:
            count[0] += 1
            if count[0] > 100:
                fail('CSSは100 rule以内で書いてください。')
            if rule.type == 'qualified-rule':
                selector = selectors(rule.prelude)
                if scope:
                    selector = ','.join(f'.{scope} {part.strip()}' for part in selector.split(','))
                out.append(f'{selector}{{{declarations(rule.content)}}}')
            elif rule.type == 'at-rule' and rule.lower_at_keyword == 'media' and rule.content is not None:
                p = meaningful(rule.prelude)
                if len(p) != 1 or p[0].type != '() block':
                    fail('@mediaは (min-width: 600px) / (max-width: 600px) の形式で書いてください。')
                v = meaningful(p[0].content)
                if len(v) != 3 or v[0].type != 'ident' or v[0].value not in {'min-width', 'max-width'} or v[1].type != 'literal' or v[1].value != ':' or v[2].type != 'dimension' or v[2].lower_unit != 'px' or not 160 <= v[2].value <= 2000:
                    fail('@mediaの幅は160〜2000pxで指定してください。')
                out.append('@media ' + tinycss2.serialize(rule.prelude) + '{' + rules(tinycss2.parse_rule_list(rule.content, skip_whitespace=True), depth+1) + '}')
            else:
                fail('CSSは通常ruleと幅による@mediaだけを使えます。@import・font・外部URLは使用できません。')
        return ''.join(out)
    return rules(tinycss2.parse_stylesheet(source, skip_whitespace=True))


def render_document(html, css, items, values):
    content = html_fragment(html, items, values)
    scope = 'niixy-layout-' + uuid.uuid4().hex
    # No size containment or forced height: content contributes its natural height.
    # Shadow DOM/containment are layout defenses, not the script security boundary.
    # HTML + CSS allowlists above are the mandatory active-content/network boundary.
    style = ':host{all:initial;display:block;contain:layout style paint;isolation:isolate;min-width:0;max-width:100%;color:#202027;background:#fff;font:16px/1.5 sans-serif}'
    style += f'.{scope}{{box-sizing:border-box;width:100%;padding:16px;overflow-wrap:anywhere}}.{scope} *{{box-sizing:border-box;max-width:100%;min-width:0}}'
    style += stylesheet(css, scope)
    return '<div data-account-layout-surface><template><style>' + style + '</style><div class="' + scope + '">' + content + '</div></template></div>'
