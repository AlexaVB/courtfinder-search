from django.test import Client
from mock import Mock, patch
from postcodeinfo import NoResults

from courtfinder.test_utils import TestCaseWithData
from search.court_search import CourtSearch, PostcodeCourtSearch, \
    is_full_postcode
from search.errors import CourtSearchError
from search.models import *
from . import postcode_valid, postcode_error


class SearchTestCase(TestCaseWithData):

    def test_is_full_postcode(self):
        self.assertTrue(all(map(is_full_postcode, [
            'EC1A 1BB', 'EC1A1BB', 'W1A 0AX', 'W1A0AX', 'M1 1AE', 'M11AE',
            'B33 8TH', 'B338TH', 'CR2 6XH', 'CR26XH', 'DN55 1PT', 'DN551PT'])))

        self.assertFalse(any(map(is_full_postcode, [
            'EC1A 1', 'EC1A1', 'W1A 0', 'W1A0', 'M1 1', 'M11', 'B33 8', 'B338',
            'CR2 6', 'CR26', 'DN55 1', 'DN551', 'EC1', 'EC', 'E', 'E1', 'B33',
            'foo', '123', 'not a postcode', 'ZZZ1 2YYY', 'Z111 2YY'])))

    def test_format_results_with_postal_address(self):
        c = Client()
        response = c.get('/search/results?q=Accrington')
        self.assertIn("Blackburn", response.content)

    def test_search_space_in_name(self):
        c = Client()
        response = c.get('/search/results?q=Accrington+Magistrates')
        self.assertIn("Accrington", response.content)

    def test_aol_page(self):
        c = Client()
        response = c.get('/search/aol')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'search/aol.jinja')
        self.assertIn('About your issue', response.content)

    def test_spoe_page_with_has_spoe(self):
        c = Client()
        response = c.get('/search/spoe?aol=children')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'search/spoe.jinja')
        self.assertIn('About your issue', response.content)

    def test_spoe_page_without_spoe(self):
        c = Client()
        response = c.get('/search/spoe?aol=crime', follow=True)
        self.assertInHTML('<h1>Enter postcode</h1>', response.content)

    def test_distance_search(self):
        with postcode_valid('lookup_postcode'):
            c = Client()
            response = c.get('/search/results?postcode=SE154UH&aol=crime')
            self.assertEqual(response.status_code, 200)

    def test_local_authority_search(self):
        with postcode_valid('lookup_postcode'):
            c = Client()
            response = c.get('/search/results?postcode=SE154UH&aol=divorce')
            self.assertEqual(response.status_code, 200)
            self.assertIn('Accrington', response.content)

    def test_results_no_query(self):
        c = Client()
        response = c.get('/search/results?q=')
        self.assertRedirects(response, '/search/address?error=noquery', 302)

    def test_results_no_postcode(self):
        c = Client()
        response = c.get('/search/results?aol=crime&postcode=')
        self.assertRedirects(
            response, '/search/postcode?error=nopostcode&aol=crime', 302)

    def test_sample_postcode_all_aols(self):
        with postcode_valid('lookup_postcode'):
            c = Client()
            response = c.get('/search/results?postcode=SE15+4UH&aol=all')
            self.assertEqual(response.status_code, 200)

    def test_sample_postcode_specific_aol(self):
        with postcode_valid('lookup_postcode'):
            c = Client()
            response = c.get('/search/results?postcode=SE15+4UH&aol=divorce')
            self.assertEqual(response.status_code, 200)

    def test_bad_aol(self):
        with postcode_valid('lookup_postcode'):
            c = Client()
            response = c.get(
                '/search/results?postcode=SE15+4UH&aol=doesntexist',
                follow=True)
            self.assertEqual(response.status_code, 400)
            self.assertIn('your browser sent a request', response.content)

    def test_inactive_court(self):
        Court.objects.create(
            name="Example2 Court",
            lat=0.0,
            lon=0.0,
            displayed=False,
        )
        c = Client()
        response = c.get('/search/results?q=Example2+Court', follow=True)
        self.assertIn('validation-error', response.content)

    def test_substring_should_not_match(self):
        c = Client()
        response = c.get('/search/results?q=ample2', follow=True)
        self.assertIn('validation-error', response.content)

    def test_too_much_whitespace_in_address_search(self):
        c = Client()
        response = c.get(
            '/search/results?q=Accrington++++Magistrates', follow=True)
        self.assertNotIn('validation-error', response.content)

    def test_regexp_city_should_match(self):
        c = Client()
        response = c.get('/search/results?q=accrington', follow=True)
        self.assertNotIn('validation-error', response.content)

    def test_scottish_postcodes(self):
        c = Client()

        with postcode_valid('lookup_postcode'):
            response = c.get('/search/results?postcode=G24PP&aol=all')
            self.assertEqual(response.status_code, 200)
            self.assertIn('<p id="scotland">', response.content)

        with postcode_valid('lookup_partial_postcode'):
            response = c.get('/search/results?postcode=G2&aol=all')
            self.assertEqual(response.status_code, 200)
            self.assertIn('<p id="scotland">', response.content)

        with postcode_valid('lookup_partial_postcode'):
            response = c.get('/search/results?postcode=AB10&aol=all')
            self.assertEqual(response.status_code, 200)
            self.assertIn('<p id="scotland">', response.content)

        with postcode_valid('lookup_postcode'):
            response = c.get('/search/results?postcode=AB10+7LY&aol=all')
            self.assertEqual(response.status_code, 200)
            self.assertIn('<p id="scotland">', response.content)

        with postcode_valid('lookup_postcode'):
            response = c.get('/search/results?postcode=BA27AY&aol=all')
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('<p id="scotland">', response.content)

    def test_partial_postcode(self):
        c = Client()
        with postcode_valid('lookup_partial_postcode'):
            response = c.get('/search/results?postcode=SE15&aol=all')
            self.assertEqual(response.status_code, 200)
            self.assertIn('<div class="search-results">', response.content)

    def test_partial_postcode_whitespace(self):
        c = Client()
        with postcode_valid('lookup_partial_postcode'):
            response = c.get('/search/results?postcode=SE15++&aol=all')
            self.assertEqual(response.status_code, 200)
            self.assertIn('<div class="search-results">', response.content)

    def test_postcode_whitespace(self):
        c = Client()
        with postcode_valid('lookup_postcode'):
            response = c.get('/search/results?postcode=++SE154UH++&aol=all')
            self.assertEqual(response.status_code, 200)
            self.assertIn('<div class="search-results">', response.content)

    def test_redirect_directive_action(self):
        rules = Mock(return_value={
            'action': 'redirect', 'target': 'search:postcode'})
        with patch('search.rules.Rules.for_view', rules), postcode_error(NoResults):
            response = Client().get('/search/results?postcode=BLARGH')
            self.assertRedirects(
                response,
                '/search/postcode?postcode=BLARGH&error=badpostcode',
                302)

    def test_internal_error(self):
        c = Client()
        error = Mock(side_effect=CourtSearchError('something went wrong'))
        with patch('search.court_search.CourtSearch.get_courts', error):
            response = c.get('/search/results.json?q=Accrington')
            self.assertEquals(500, response.status_code)
            self.assertIn("something went wrong", response.content)

    def test_search_no_postcode_nor_q(self):
        c = Client()
        response = c.get('/search/results')
        self.assertRedirects(response, '/search/', 302)

    def test_postcode_to_local_authority_short_postcode(self):
        with postcode_valid('lookup_partial_postcode'):
            self.assertEqual(
                1,
                len(PostcodeCourtSearch(
                    postcode='SE15', area_of_law='divorce').get_courts()))

    def test_local_authority_search_ordered(self):
        with postcode_valid('lookup_postcode'):
            self.assertEqual(
                "Accrington Magistrates' Court",
                PostcodeCourtSearch(
                    postcode='SE154UH', area_of_law='divorce'
                ).get_courts()[0].name)

    def test_proximity_search(self):
        with postcode_valid('lookup_postcode'):
            self.assertNotEqual(
                PostcodeCourtSearch(
                    postcode='SE154UH', area_of_law='divorce'
                ).get_courts(), [])

    def test_court_address_search_error(self):
        error = Mock(side_effect=CourtSearchError('something went wrong'))
        with patch('search.court_search.CourtSearch.get_courts', error):
            c = Client()
            with self.assertRaises(CourtSearchError):
                c.get('/search/results?q=Accrington')

    def test_court_postcode_search_error(self):
        error = Mock(side_effect=CourtSearchError('something went wrong'))
        with patch('search.court_search.CourtSearch.get_courts', error):
            c = Client()
            with self.assertRaises(CourtSearchError):
                c.get('/search/results?postcode=SE15+4PE')

    def test_address_search(self):
        c = Client()
        response = c.get('/search/results?q=Road')
        self.assertEqual(response.status_code, 200)

    def test_partial_word_match(self):
        c = Client()
        response = c.get('/search/results?q=accrington+court')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Accrington Magistrates', response.content)

    def test_unordered_word_match(self):
        c = Client()
        response = c.get('/search/results?q=magistrates+court+accrington')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Accrington Magistrates', response.content)

    def test_empty_postcode(self):
        c = Client()
        response = c.get('/search/results?postcode=')
        self.assertEqual(response.status_code, 302)

    def test_broken_postcode(self):
        c = Client()
        with postcode_error(NoResults):
            response = c.get((
                '/search/results?aol=divorce&spoe=continue'
                '&postcode=NW3+%25+au'),
                follow=True)
            self.assertEqual(200, response.status_code)
            self.assertIn('NW3  au', response.content)

    def test_ni(self):
        c = Client()
        with postcode_valid('lookup_partial_postcode'):
            response = c.get(
                '/search/results?postcode=bt2&aol=divorce',
                follow=True)
            self.assertIn(
                "this tool does not return results for Northern Ireland",
                response.content)

    def test_money_claims(self):
        c = Client()
        with postcode_valid('lookup_postcode'):
            response = c.get(
                '/search/results?postcode=sw1h9aj&spoe=start&aol=money-claims')
            self.assertIn("CCMCC", response.content)

    def test_ni_immigration(self):
        c = Client()
        with postcode_valid('lookup_partial_postcode'):
            response = c.get(
                '/search/results?postcode=bt2&aol=immigration', follow=True)
            self.assertNotIn(
                "this tool does not return results for Northern Ireland",
                response.content)

    def test_court_postcodes(self):
        court = Court.objects.get(name="Accrington Magistrates' Court")
        self.assertEqual(len(court.postcodes_covered()), 1)

    def test_court_local_authority_aol_covered(self):
        court = Court.objects.get(name="Accrington Magistrates' Court")
        aol = AreaOfLaw.objects.get(name="Divorce")
        court_aol = CourtAreaOfLaw.objects.get(court=court, area_of_law=aol)
        self.assertEqual(len(court_aol.local_authorities_covered()), 1)
        self.assertEqual(str(court_aol.local_authorities_covered()[0]),
                         "Accrington Magistrates' Court covers Southwark Borough Council for Divorce")

    def test_models_unicode(self):
        court = Court.objects.get(name="Accrington Magistrates' Court")
        self.assertEqual(str(court), "Accrington Magistrates' Court")
        cat = CourtAttributeType.objects.create(name="cat")
        self.assertEqual(str(cat), "cat")
        ca = CourtAttribute.objects.create(court=court, attribute_type=cat, value="cav")
        self.assertEqual(str(ca), "Accrington Magistrates' Court.cat = cav")
        aol, _ = AreaOfLaw.objects.get_or_create(name='Divorce', slug='divorce')
        self.assertEqual(str(aol), "Divorce")
        self.assertEqual(aol.slug, "divorce")
        aols = CourtAreaOfLaw.objects.create(court=court, area_of_law=aol)
        self.assertEqual(str(aols), "Accrington Magistrates' Court deals with Divorce (spoe: False)")
        town = Town.objects.create(name="Hobbittown", county="Shire")
        self.assertEqual(str(town), "Hobbittown (Shire)")
        address_type = AddressType.objects.create(name="Postal")
        self.assertEqual(str(address_type), "Postal")
        court_address = CourtAddress.objects.create(address_type=address_type,
                                                    court=court,
                                                    address="The court address",
                                                    postcode="CF34RR",
                                                    town=town)
        self.assertEqual(str(court_address),
                         "Postal for Accrington Magistrates' Court is The court address, CF34RR, Hobbittown")
        contact = Contact.objects.create(name="Enquiries", number="0123456789")
        self.assertEqual(str(contact), "Enquiries: 0123456789")
        court_type = CourtType.objects.create(name="crown court")
        self.assertEqual(str(court_type), "crown court")
        court_contact = CourtContact.objects.create(contact=contact, court=court)
        self.assertEqual(str(court_contact), "Enquiries for Accrington Magistrates' Court is 0123456789")
        court_court_types = CourtCourtType.objects.create(court=court,
                                                          court_type=court_type)
        self.assertEqual(str(court_court_types), "Court type for Accrington Magistrates' Court is crown court")
        court_postcodes = CourtPostcode.objects.create(court=court,
                                                       postcode="BR27AY")
        self.assertEqual(str(court_postcodes), "Accrington Magistrates' Court covers BR27AY")
        local_authority = LocalAuthority.objects.create(name="Southwark Borough Council")
        self.assertEqual(str(local_authority), "Southwark Borough Council")
        court_local_authority_aol = CourtLocalAuthorityAreaOfLaw(court=court,
                                                                 area_of_law=aol,
                                                                 local_authority=local_authority)
        self.assertEqual(str(court_local_authority_aol),
                         "Accrington Magistrates' Court covers Southwark Borough Council for Divorce")
        facility = Facility.objects.create(name="sofa", description="comfy leather")
        self.assertEqual(str(facility), "sofa: comfy leather")
        court_facility = CourtFacility.objects.create(court=court, facility=facility)
        self.assertEqual(str(court_facility), "%s has facility %s" % (court.name, facility))
        opening_time = OpeningTime.objects.create(description="open 7/7")
        self.assertEqual(str(opening_time), "open 7/7")
        court_opening_time = CourtOpeningTime.objects.create(court=court, opening_time=opening_time)
        self.assertEqual(str(court_opening_time), "%s has facility %s" % (court.name, opening_time))
        email = Email.objects.create(description="enquiries", address="a@b.com")
        self.assertEqual(str(email), "enquiries: a@b.com")
        court_email = CourtEmail.objects.create(court=court, email=email)
        self.assertEqual(str(court_email), "%s has email: %s" % (court.name, email.description))
        data_status = DataStatus.objects.create(data_hash="wer38hr3hr37hr")
        self.assertEqual(str(data_status), "Current data hash: %s, last update: %s" %
                         (data_status.data_hash, data_status.last_ingestion_date))
        parking_info = ParkingInfo.objects.create(onsite="foo", offsite="bar", blue_badge="baz")
        self.assertEqual(str(parking_info), "Parking onsite: foo, Parking offsite: bar, Parking blue-badge: baz")

    def test_data_status(self):
        c = Client()
        response = c.get('/search/datastatus')
        self.assertEqual(200, response.status_code)
        self.assertIn('901ef05ce3b2c1eac3c9a23005a6477b', response.content)