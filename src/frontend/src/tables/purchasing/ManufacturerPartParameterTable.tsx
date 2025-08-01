import { t } from '@lingui/core/macro';
import { useCallback, useMemo, useState } from 'react';

import {
  type RowAction,
  RowDeleteAction,
  RowEditAction
} from '@lib/components/RowActions';
import { ApiEndpoints } from '@lib/enums/ApiEndpoints';
import { UserRoles } from '@lib/enums/Roles';
import { apiUrl } from '@lib/functions/Api';
import type { TableColumn } from '@lib/types/Tables';
import { AddItemButton } from '../../components/buttons/AddItemButton';
import { useManufacturerPartParameterFields } from '../../forms/CompanyForms';
import {
  useCreateApiFormModal,
  useDeleteApiFormModal,
  useEditApiFormModal
} from '../../hooks/UseForm';
import { useTable } from '../../hooks/UseTable';
import { useUserState } from '../../states/UserState';
import { InvenTreeTable } from '../InvenTreeTable';

export default function ManufacturerPartParameterTable({
  params
}: Readonly<{
  params: any;
}>) {
  const table = useTable('manufacturer-part-parameter');
  const user = useUserState();

  const tableColumns: TableColumn[] = useMemo(() => {
    return [
      {
        accessor: 'name',
        title: t`Name`,
        sortable: true,
        switchable: false
      },
      {
        accessor: 'value',
        title: t`Value`,
        sortable: true,
        switchable: false
      },
      {
        accessor: 'units',
        title: t`Units`,
        sortable: false,
        switchable: true
      }
    ];
  }, []);

  const fields = useManufacturerPartParameterFields();

  const [selectedParameter, setSelectedParameter] = useState<
    number | undefined
  >(undefined);

  const createParameter = useCreateApiFormModal({
    url: ApiEndpoints.manufacturer_part_parameter_list,
    title: t`Add Parameter`,
    fields: fields,
    table: table,
    initialData: {
      manufacturer_part: params.manufacturer_part
    }
  });

  const editParameter = useEditApiFormModal({
    url: ApiEndpoints.manufacturer_part_parameter_list,
    pk: selectedParameter,
    title: t`Edit Parameter`,
    fields: fields,
    table: table
  });

  const deleteParameter = useDeleteApiFormModal({
    url: ApiEndpoints.manufacturer_part_parameter_list,
    pk: selectedParameter,
    title: t`Delete Parameter`,
    table: table
  });

  const rowActions = useCallback(
    (record: any): RowAction[] => {
      return [
        RowEditAction({
          hidden: !user.hasChangeRole(UserRoles.purchase_order),
          onClick: () => {
            setSelectedParameter(record.pk);
            editParameter.open();
          }
        }),
        RowDeleteAction({
          hidden: !user.hasDeleteRole(UserRoles.purchase_order),
          onClick: () => {
            setSelectedParameter(record.pk);
            deleteParameter.open();
          }
        })
      ];
    },
    [user]
  );

  const tableActions = useMemo(() => {
    return [
      <AddItemButton
        key='add-parameter'
        tooltip={t`Add Parameter`}
        onClick={() => {
          createParameter.open();
        }}
        hidden={!user.hasAddRole(UserRoles.purchase_order)}
      />
    ];
  }, [user]);

  return (
    <>
      {createParameter.modal}
      {editParameter.modal}
      {deleteParameter.modal}
      <InvenTreeTable
        url={apiUrl(ApiEndpoints.manufacturer_part_parameter_list)}
        tableState={table}
        columns={tableColumns}
        props={{
          params: {
            ...params
          },
          rowActions: rowActions,
          tableActions: tableActions
        }}
      />
    </>
  );
}
