import copy
import os

from django.conf import settings
import shutil

from django.urls import reverse
from django.test.utils import override_settings
from selenium.webdriver.support.wait import WebDriverWait

from zds.tutorialv2.models.database import Validation

BASE_DIR = settings.BASE_DIR

overridden_zds_app = copy.deepcopy(settings.ZDS_APP)
overridden_zds_app['content']['repo_private_path'] = os.path.join(BASE_DIR, 'contents-private-test')
overridden_zds_app['content']['repo_public_path'] = os.path.join(BASE_DIR, 'contents-public-test')
overridden_zds_app['content']['extra_content_generation_policy'] = 'SYNC'
overridden_zds_app['content']['build_pdf_when_published'] = False


class override_for_contents(override_settings):
    def __init__(self, **kwargs):
        kwargs.update(MEDIA_ROOT=os.path.join(BASE_DIR, 'media-test'), ZDS_APP=overridden_zds_app)

        if 'ES_ENABLED' not in kwargs:
            kwargs.update(ES_ENABLED=False)

        super().__init__(**kwargs)


class TutorialTestMixin:

    overridden_zds_app = overridden_zds_app

    def clean_media_dir(self):
        shutil.rmtree(self.overridden_zds_app['content']['repo_private_path'], ignore_errors=True)
        shutil.rmtree(self.overridden_zds_app['content']['repo_public_path'], ignore_errors=True)
        shutil.rmtree(self.overridden_zds_app['content']['extra_content_watchdog_dir'], ignore_errors=True)

        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def tearDown(self):
        self.clean_media_dir()
        self.client.logout()

    def login(self, user, password):
        success = self.client.login(username=user.username, password=password)
        self.assertEqual(success, True)

    def logout(self):
        self.client.logout()

    def access_content_display_page(self, kwargs):
        return self.client.get(
            reverse('content:view', kwargs=kwargs),
            follow=False)

    def access_content_creation_page(self, _type='TUTORIAL'):
        return self.client.get(
            reverse(f'content:create-{_type.lower()}'),
            follow=False)

    def create_content(self, content_informations):
        _type = content_informations['type'].lower()
        return self.client.post(
            reverse(f'content:create-{_type}'),
            content_informations,
            follow=False
        )

    def get_content_informations(self, content):
        f = lambda obj: obj.pk
        versioned = content.load_version()
        kwargs = {}
        kwargs['title']        = versioned.title
        kwargs['introduction'] = versioned.get_introduction()
        kwargs['conclusion']   = versioned.get_conclusion()
        kwargs['description']  = versioned.description
        kwargs['licence']      = versioned.licence.pk
        kwargs['subcategory']  = set(map(f, set(versioned.subcategory.all())))
        kwargs['type']         = versioned.type
        kwargs['authors']      = set(versioned.authors.all())
        return kwargs

    def check_content_informations(self, content, informations_to_check):
        # comparison_functions instead of functions.
        # with comparison_functions['title'] = lambda v, kw : self.assertEqual(v.title, kw['title'])
        #
        content_informations = self.get_content_informations(content)
        for key in informations_to_check:
            if key in content_informations:
                self.assertEqual(content_informations[key], informations_to_check[key])

    def access_content_edition_page(self, kwargs):
        return self.client.get(
            reverse('content:edit', kwargs=kwargs),
            follow=False)

    def edit_content(self, kwargs, content_informations):
        return self.client.post(
            reverse('content:edit', kwargs=kwargs),
            content_informations,
            follow=False)

    def delete_content(self, kwargs):
        return self.client.post(
            reverse('content:delete', kwargs=kwargs),
            follow=False)

class TutorialFrontMixin:
    def login(self, profile):
        """
        TODO: This is definitely way too slow. Fasten this.
        """
        selenium = self.selenium
        find_element = selenium.find_element_by_css_selector

        selenium.get(self.live_server_url + reverse('member-login'))

        username = find_element('.content-container input#id_username')
        password = find_element('.content-container input#id_password')
        username.send_keys(profile.user.username)
        password.send_keys('hostel77')

        find_element('.content-container button[type=submit]').click()

        # Wait until the user is logged in (this raises if the element
        # is not found).

        find_element('.header-container .logbox #my-account .username')

    def login_author(self):
        self.login(self.user_author.profile)

    def login_staff(self):
        self.login(self.user_staff.profile)

    def logout(self):
        find_element = self.selenium.find_element_by_css_selector
        find_element('#my-account').click()
        find_element('form[action="/membres/deconnexion/"] button').click()

    def ask_validation(self):
        find_element = self.selenium.find_element_by_css_selector
        self.selenium.get(self.live_server_url + self.content.get_absolute_url())
        find_element('a[href="#ask-validation"]').click()
        find_element('#id_text').send_keys('Coucou.')
        find_element('#ask-validation button[type="submit"]').click()

    def take_reservation(self):
        find_element = self.selenium.find_element_by_css_selector
        self.selenium.get(self.live_server_url + self.content.get_absolute_url())
        validation = Validation.objects.filter(content=self.content).first()
        find_element('form[action="/validations/reserver/{}/"] button'.format(validation.pk)).click()

    def validate(self):
        find_element = self.selenium.find_element_by_css_selector
        self.selenium.get(self.live_server_url + self.content.get_absolute_url())
        validation = Validation.objects.filter(content=self.content).first()
        find_element('a[href="#valid-publish"]').click()
        find_element('form#valid-publish #id_text').send_keys('Coucou.')
        find_element('form[action="/validations/accepter/{}/"] button'.format(validation.pk)).click()

    def wait_element_attribute_change(self, locator, attribute, initial_value, time):
        return WebDriverWait(self.selenium, time) \
            .until(AttributeHasChanged(locator, attribute, initial_value))


class AttributeHasChanged:
    def __init__(self, locator, attribute_name, initial_value):
        self.locator = locator
        self.attribute_name = attribute_name
        self.initial_value = initial_value

    def __call__(self, driver):
        element = driver.find_element(*self.locator)
        return element.get_attribute(self.attribute_name) != self.initial_value
