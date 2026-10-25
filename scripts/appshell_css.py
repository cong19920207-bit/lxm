"""Scope extracted page rules; preserve declarations, media queries and keyframes."""
import re


def _delimiter(text, start, wanted):
    quote = None
    depth = 0
    i = start
    while i < len(text):
        char = text[i]
        if quote:
            if char == '\\':
                i += 2
                continue
            if char == quote:
                quote = None
        elif text.startswith('/*', i):
            end = text.find('*/', i + 2)
            if end < 0:
                raise ValueError('Unclosed CSS comment')
            i = end + 2
            continue
        elif char in '\"\'':
            quote = char
        elif char in '([':
            depth += 1
        elif char in ')]':
            depth -= 1
        elif not depth and char in wanted:
            return i
        i += 1
    return len(text)


def scope_css(text, page):
    if not re.fullmatch('[a-z]+', page):
        raise ValueError('Invalid page name')
    result, start = [], 0
    while start < len(text):
        opening = _delimiter(text, start, '{;')
        if opening == len(text):
            result.append(text[start:])
            break
        if text[opening] == ';':
            result.append(text[start:opening + 1])
            start = opening + 1
            continue
        end, level = opening + 1, 1
        while level:
            end = _delimiter(text, end, '{}')
            if end == len(text):
                raise ValueError('Unclosed CSS rule')
            level += 1 if text[end] == '{' else -1
            end += 1
        header, body = text[start:opening], text[opening + 1:end - 1]
        stripped = re.sub(r'/\*.*?\*/', '', header, flags=re.S).strip()
        if stripped.startswith(('@media', '@supports', '@container', '@layer')):
            body = scope_css(body, page)
        elif not stripped.startswith('@'):
            selectors, position = [], 0
            while position < len(header):
                comma = _delimiter(header, position, ',')
                selector = header[position:comma].strip()
                comments = re.match(r'(?:\s*/\*.*?\*/)*\s*', selector, flags=re.S)[0]
                selector = selector[len(comments):]
                if selector.startswith('html'):
                    selector = 'html[data-app-route="' + page + '"]' + selector[4:]
                elif selector.startswith('body') or selector.startswith(':root'):
                    selector = 'html[data-app-route="' + page + '"] ' + selector.replace(':root', '', 1).strip()
                else:
                    selector = ':where([data-app-page="' + page + '"]) ' + selector
                selectors.append(comments + selector)
                position = comma + 1
            header = '\n' + ',\n'.join(selectors) + ' '
        result.append(header + '{' + body + '}')
        start = end
    return ''.join(result)
