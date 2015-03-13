# -- coding: utf-8 --
# ===========================================================================
# eXe
# Copyright 2015, Pedro Peña Pérez, Open Phoenix IT
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
# ===========================================================================
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from nevow import rend, inevow, url
from twisted.web import http
from exe import globals as G

import logging

log = logging.getLogger(__name__)


def init_saml_auth(req):
    saml_config_dir = G.application.config.configDir/'saml'
    if not saml_config_dir.isdir():
        template_config = G.application.config.exePath.parent/'saml_template'
        if template_config.exists():
            template_config.copytree(saml_config_dir)
        else:
            return None
    auth = OneLogin_Saml2_Auth(req, custom_base_path=saml_config_dir)
    return auth


def prepare_nevow_request(request):
    get_data, post_data = {}, {}
    for k, v in request.args.iteritems():
        get_data[k] = v[0]
        post_data[k] = v[0]
    scheme = request.received_headers.get('x-forwarded-proto', 'http')
    host = request.received_headers.get('x-forwarded-host', request.getHeader('host'))
    port = host.split(':')
    port = int(port[1]) if len(port) > 1 else (80 if scheme == 'http' else 443)
    return {
        'http_host': host,
        'scheme': scheme,
        'server_port': port,
        'script_name': request.path,
        'get_data': get_data,
        'post_data': post_data
    }


class ACSPage(rend.Page):
    def renderHTTP(self, context):
        request = inevow.IRequest(context)
        req = prepare_nevow_request(request)
        auth = init_saml_auth(req)
        auth.process_response()
        errors = auth.get_errors()
        if len(errors) == 0 and auth.is_authenticated():
            attributes = auth.get_attributes()
            session = request.getSession()
            session.setUser(attributes['email'][0])
            return url.URL.fromString(req['post_data']['RelayState'])
        request.setResponseCode(http.INTERNAL_SERVER_ERROR)
        return auth.get_last_error_reason()


class SAMLPage(rend.Page):
    name = 'saml'

    def __init__(self, parent):
        parent.putChild(self.name, self)
        rend.Page.__init__(self)

    child_acs = ACSPage('acs')

    def renderHTTP(self, context):
        request = inevow.IRequest(context)
        req = prepare_nevow_request(request)
        auth = init_saml_auth(req)
        if auth:
            start_url = auth.login('%s://%s' % (req['scheme'], req['http_host']))
            return url.URL.fromString(start_url)
        else:
            return 'SAML authentication needs a saml configuration directory at %s. See an example ' \
                   '<a href="https://forja.cenatic.es/plugins/scmgit/cgi-bin/gitweb.cgi?p=iteexe/iteexe.git;a=tree;f=saml_template;hb=ws">' \
                   'here</a>' % (G.application.config.configDir/'saml').encode('utf-8')