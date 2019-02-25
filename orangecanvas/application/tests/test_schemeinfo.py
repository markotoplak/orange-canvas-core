from ...scheme import Scheme
from ..schemeinfo import SchemeInfoDialog
from ...gui import test


class TestSchemeInfo(test.QAppTestCase):
    def test_scheme_info(self):
        scheme = Scheme(title="A Scheme", description="A String\n")
        dialog = SchemeInfoDialog()
        dialog.setScheme(scheme)

        status = dialog.exec_()

        if status == dialog.Accepted:
            self.assertEqual(scheme.title.strip(),
                             dialog.editor.name_edit.text().strip())
            self.assertEqual(scheme.description,
                             dialog.editor.desc_edit.toPlainText().strip())
