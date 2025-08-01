"""Label printing plugin that provides support for printing using a label printer machine."""

from typing import cast

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from rest_framework import serializers

from common.models import InvenTreeUserSetting
from InvenTree.serializers import DependentField
from InvenTree.tasks import offload_task
from machine.machine_types import LabelPrinterBaseDriver, LabelPrinterMachine
from plugin import InvenTreePlugin
from plugin.machine import call_machine_function, registry
from plugin.mixins import LabelPrintingMixin
from report.models import LabelTemplate


def get_machine_and_driver(machine_pk: str):
    """Get the driver by machine pk and ensure that it is a label printing driver."""
    machine = registry.get_machine(machine_pk)

    # machine should be valid due to the machine select field validator
    if machine is None:  # pragma: no cover
        return None, None

    if machine.SLUG != 'label-printer':  # pragma: no cover
        return None, None

    machine = cast(LabelPrinterMachine, machine)
    driver = machine.driver

    if driver is None:  # pragma: no cover
        return machine, None

    return machine, cast(LabelPrinterBaseDriver, driver)


def get_last_used_printers(user):
    """Get the last used printers for a specific user."""
    return [
        printer
        for printer in cast(
            str,
            InvenTreeUserSetting.get_setting(
                'LAST_USED_PRINTING_MACHINES', '', user=user
            ),
        ).split(',')
        if printer
    ]


class InvenTreeLabelPlugin(LabelPrintingMixin, InvenTreePlugin):
    """Builtin plugin for machine label printing.

    This enables machines to print labels.
    """

    NAME = 'InvenTreeLabelMachine'
    TITLE = _('InvenTree machine label printer')
    DESCRIPTION = _('Provides support for printing using a machine')
    VERSION = '1.0.0'
    AUTHOR = _('InvenTree contributors')

    def print_labels(self, label: LabelTemplate, output, items, request, **kwargs):
        """Print labels implementation that calls the correct machine driver print_labels method."""
        machine, driver = get_machine_and_driver(
            kwargs['printing_options'].get('machine', '')
        )

        # the driver and machine should be valid due to the machine select field validator
        if driver is None or machine is None:  # pragma: no cover
            return None

        print_kwargs = {
            **kwargs,
            'printing_options': kwargs['printing_options'].get('driver_options', {}),
        }

        if output:
            user = output.user
        elif request:
            user = request.user
        else:
            user = None

        # Save the current used printer as last used printer
        # Only the last ten used printers are saved so that this list doesn't grow infinitely
        if user and user.is_authenticated:
            last_used_printers = get_last_used_printers(user)
            machine_pk = str(machine.pk)
            if machine_pk in last_used_printers:
                last_used_printers.remove(machine_pk)
            last_used_printers.insert(0, machine_pk)
            InvenTreeUserSetting.set_setting(
                'LAST_USED_PRINTING_MACHINES',
                ','.join(last_used_printers[:10]),
                user=user,
            )

        offload_task(
            call_machine_function,
            machine.pk,
            'print_labels',
            label,
            items,
            output=output,
            force_sync=settings.TESTING or driver.USE_BACKGROUND_WORKER,
            group='plugin',
            **print_kwargs,
        )

        # Inform the user that the process has been offloaded to the printer
        if output:
            output.mark_complete()

    class PrintingOptionsSerializer(serializers.Serializer):
        """Printing options serializer that adds a machine select and the machines options."""

        def __init__(self, *args, **kwargs):
            """Custom __init__ method to dynamically override the machine choices based on the request."""
            super().__init__(*args, **kwargs)

            # TODO @matmair Re-enable this when the need is clear
            # view = kwargs['context']['view']
            template = None  # view.get_object()
            items_to_print = None  # view.get_items()

            # get all available printers for each driver
            machines: list[LabelPrinterMachine] = []
            for driver in cast(
                list[LabelPrinterBaseDriver], registry.get_drivers('label-printer')
            ):
                machines.extend(
                    driver.get_printers(
                        template, items_to_print, request=kwargs['context']['request']
                    )
                )

            # sort the last used printers for the user to the top
            user = kwargs['context']['request'].user
            last_used_printers = get_last_used_printers(user)[::-1]
            machines = sorted(
                machines,
                key=lambda m: last_used_printers.index(str(m.pk))
                if str(m.pk) in last_used_printers
                else -1,
                reverse=True,
            )

            choices = [(str(m.pk), self.get_printer_name(m)) for m in machines]

            # if there are choices available, use the first as default
            if len(choices) > 0:
                self.fields['machine'].default = choices[0][0]

                # add 'last used' flag to the first choice
                if choices[0][0] in last_used_printers:
                    choices[0] = (
                        choices[0][0],
                        choices[0][1] + ' (' + _('last used') + ')',
                    )

            self.fields['machine'].choices = choices

        def get_printer_name(self, machine: LabelPrinterMachine):
            """Construct the printers name."""
            name = machine.name

            if machine.location:
                name += f' @ {machine.location.name}'

            return name

        machine = serializers.ChoiceField(choices=[])

        driver_options = DependentField(
            label=_('Options'),
            depends_on=['machine'],
            field_serializer='get_driver_options',
            required=False,
        )

        def get_driver_options(self, fields):
            """Returns the selected machines serializer."""
            _, driver = get_machine_and_driver(fields['machine'])

            if driver is None:
                return None

            return driver.get_printing_options_serializer(
                self.context['request'], context=self.context
            )
