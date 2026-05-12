"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import type { QueryResult } from "@/lib/api";

interface Props {
  result: QueryResult;
}

function fmtColName(col: string): string {
  return col.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function fmtCell(v: unknown) {
  if (v == null) return <span className="text-gray-300">—</span>;
  if (typeof v === "number") return v.toLocaleString();
  return String(v);
}

export function ResultsTable({ result }: Props) {
  const { columns, rows } = result;
  const helper = createColumnHelper<unknown[]>();

  const tableCols = columns.map((col, i) =>
    helper.accessor((row) => (row as unknown[])[i], {
      id: col,
      header: fmtColName(col),
      cell: (info) => fmtCell(info.getValue()),
    })
  );

  const table = useReactTable({
    data: rows as unknown[][],
    columns: tableCols,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => (
                <th
                  key={h.id}
                  className="px-4 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap"
                >
                  {flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="hover:bg-gray-50">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 py-2.5 text-gray-800 whitespace-nowrap">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
