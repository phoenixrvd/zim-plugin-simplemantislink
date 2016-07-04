# coding=utf-8

from zim.actions import action
from zim.gui import Dialog, MessageDialog
from zim.gui.widgets import InputForm
from zim.plugins import PluginClass, WindowExtension, extends
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
    import BeautifulSoup
except ImportError:
    BeautifulSoup = None

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
    def check_dependencies(klass):
        return bool(requests or BeautifulSoup.BeautifulSoup or re), [
            ('requests', not requests is None, True),
            ('BeautifulSoup', not BeautifulSoup.BeautifulSoup is None, True),
            ('re', not re is None, True)
        ]


@extends('MainWindow')
class MainWindowExtension(WindowExtension):
    uimanager_xml = '''
        <ui>
            <menubar name='menubar'>
                <menu action='tools_menu'>
                    <placeholder name='plugin_items'>
                        <menuitem action='mantis_button_clicked'/>
                    </placeholder>
                </menu>
            </menubar>
        </ui>
    '''

    def __init__(self, plugin, window):
        WindowExtension.__init__(self, plugin, window)

        # Define the bugtracker object as global, for the performance purpose
        plugin.bt = Mantis()

    @action(
            _('Insert Mantis Link'),
            readonly=True,
            accelerator='<Control><Shift>M'
    )  # T: menu item
    def mantis_button_clicked(self):
        '''Run the TicketDialog'''
        TicketDialog(self.window, self.plugin, self.window.pageview).run()


class RequestError(Exception):
    pass

class TicketDialog(Dialog):
    def __init__(self, ui, notebook, pageview):
        self.notebook = notebook
        self.bt = notebook.bt
        self.pageview = pageview
        self.ui = ui

        Dialog.__init__(
                self,
                ui,
                _('Insert Ticket ID'),  # T: Dialog title
                button=(_('_Insert'), 'gtk-ok'),  # T: Button label
                defaultwindowsize=(245, 120)
        )

        self.form = InputForm(notebook=notebook)
        self.vbox.pack_start(self.form, False)
        self.form.add_inputs((
            ('ticket', 'string', _('ID')),  # T: Ticket ID
        ))

    def do_response_ok(self):
        self.bt.setup_config(self.notebook.preferences)

        try:
            ticket_data = self.bt.get_ticket_data(self.form['ticket'])
            buffer = self.pageview.view.get_buffer()
            buffer.insert_link_at_cursor(ticket_data['ticket'], ticket_data['url'])
            buffer.insert_at_cursor(" " + ticket_data['title'] + "\n")
        except RequestError as e:
            self.do_close(self)
            MessageDialog(self, e.message).run()


class BugTracker:
    def __init__(self):
        pass

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
            return BeautifulSoup.BeautifulSoup(response.content)
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
        ticket_title = soup.find('td', text=re.compile(ur'[0-9]{7}:(.*)', re.DOTALL))
        ticket_title_text = ''
        if ticket_title:
            ticket_title_text = re.sub('[0-9]{7}:| - MantisBT', '', ticket_title)

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