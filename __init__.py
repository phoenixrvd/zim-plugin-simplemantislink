# coding=utf-8
from zim.actions import action
from zim.gui.pageview import PageViewExtension
from zim.gui.widgets import Dialog, MessageDialog
from zim.plugins import PluginClass
from abc import abstractmethod

# Global resources including
#
# If the dependencies can not be resolved, the plugin shall not be installed.
# @see SimpleMantisLinkPlugin.check_dependencies()

try:
    import requests
except ImportError:
    requests = None

try:
    import re
except ImportError:
    re = None

try:
    import bs4
except ImportError:
    bs4 = None


class SimpleMantisLinkPlugin(PluginClass):
    plugin_info = {
        'name': _('Simple Mantis Link'),  # T: plugin name
        'description': _('Entry link to mantis ticket, without switching into Browser.'),  # T: plugin description
        'author': 'Viacheslav Wolf',
        'help': 'Plugins:Simple Mantis Link',
    }

    plugin_preferences = (
        ('url', 'string', _('URL'), 'http://'),  # T: Label for plugin preference
        ('user', 'string', _('Login'), ''),  # T: Label for plugin preference
        ('password', 'password', _('Password'), ''),  # T: Label for plugin preference
    )

    @classmethod
    def check_dependencies(cls):
        return bool(requests and bs4 and re), [
            ('requests', requests is not None, True),
            ('bs4', bs4 is not None, True),
            ('re', re is not None, True)
        ]


class SimpleMantisLinkPageViewExtension(PageViewExtension):

    @action(_('Mantis Link'), accelerator='<Control><Shift>M', menuhints='insert')  # T: Menu item
    def mantis_button_clicked(self):
        TicketDialog(self, Mantis()).run()


class RequestError(Exception):
    pass


class BugTracker:
    session = None

    # Required-Setting for login
    # can be setted from map
    # @see Tracker.setup_config
    url = "https://www.mantisbt.org/"
    user = ""
    password = ""

    def setup_config(self, config):
        for (item, value) in config.items():
            setattr(self, item, value)

    def get_ticket_data(self, ticket_id):

        # all requests have a same http - Session
        if not self.session:
            self.session_start()

        ticket_url = self.url + self.get_ticket_path(ticket_id)
        response = self.do_request(ticket_url)

        # if log form response, session timed out. Login again.
        if not self.is_login_valid(response):
            self.session_start()
            response = self.do_request(ticket_url)

        ticket_data = self.parse_ticket_page(response, ticket_url, ticket_id)
        return ticket_data

    def session_start(self):
        login_url = self.url + self.get_login_path()
        login_data = self.get_login_post_data()
        response = self.do_request(login_url, login_data)

        if not self.is_login_valid(response):
            raise RequestError(_('Login name or password is incorrect. Please check the plugin settings.'))

    def do_request(self, url, post_data=None):

        if post_data is None:
            post_data = {}

        if not self.session:
            self.session = requests.session()

        try:
            response = self.session.post(url, data=post_data)
            return bs4.BeautifulSoup(response.content)
        except:
            raise RequestError(_('Page is unreachable. Please check the URL in plugin settings.'))

    @abstractmethod
    def is_login_valid(self, content):
        """Check the content after login"""
        pass

    @abstractmethod
    def parse_ticket_page(self, content, url, ticket):
        return {
            'ticket': ticket,
            'title': '',
            'url': url
        }

    @abstractmethod
    def get_login_path(self):
        """Returned the login URL suffix ()"""
        return "login.php"

    @abstractmethod
    def get_ticket_path(self, ticket_id):
        """Returned the ticket URL suffix ()"""
        return "bug.php?bug=" + ticket_id

    def get_login_post_data(self):
        return {
            'password': self.password,
            'username': self.user
        }


class Mantis(BugTracker):
    def get_ticket_path(self, ticket_id):
        return "view.php?id=" + ticket_id

    def is_login_valid(self, soup):
        return soup.findAll('input', attrs={'name': 'password'}).__len__() == 0

    def get_login_path(self):
        return "login.php"

    def parse_ticket_page(self, soup, url, ticket):
        ticket_title = soup.find('td', text=re.compile(r'[0-9]{7}:(.*)', re.DOTALL))
        ticket_title_text = ''
        if ticket_title:
            ticket_title_text = re.sub('[0-9]{7}:| - MantisBT', '', ticket_title.text)

        return {
            'ticket': ticket,
            'title': ticket_title_text.strip(),
            'url': url
        }

    def get_login_post_data(self):
        return {
            'password': self.password,
            'username': self.user
        }


class TicketDialog(Dialog):
    def __init__(self, parent: PageViewExtension, bt: BugTracker):
        self.notebook = parent.plugin
        self.bt = bt
        self.textview = parent.pageview.textview
        self.ui = parent

        Dialog.__init__(self, parent, title=_('Insert Ticket ID'), button=_('_Insert'))

        self.add_form((
            ('ticket', 'string', _('ID')),  # T: Ticket ID
        ), {})

    def do_response_ok(self):
        self.bt.setup_config(self.notebook.preferences)

        # get the ticket ID and prevent changes during http request
        input = self.form.widgets.get('ticket')
        input.set_editable(False)
        ticket = input.get_text()
        self.do_close(self)

        # by empty string do nothing
        if not ticket:
            return True

        try:
            # Do Request to web page an set the response data formatted at cursor position
            ticket_data = self.bt.get_ticket_data(ticket)
            buffer = self.textview.get_buffer()
            buffer.insert_link_at_cursor(ticket_data['ticket'], ticket_data['url'])
            buffer.insert_at_cursor(" " + ticket_data['title'] + "\n")
        except RequestError as e:
            MessageDialog(self, str(e)).run()

        return True
