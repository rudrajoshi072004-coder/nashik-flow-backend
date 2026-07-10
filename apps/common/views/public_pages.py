from django.views.generic import TemplateView


class DeleteAccountView(TemplateView):
    template_name = "common/delete_account.html"
