# Manual Payment Button - XPath Troubleshooting

If the button doesn't appear, try these alternative xpaths in
`views/hr_payslip_views.xml` depending on your Odoo 19 version:

## Option 1 (Default - before Cancel):
    <xpath expr="//button[@name='action_payslip_cancel']" position="before">

## Option 2 (After Pay button):
    <xpath expr="//button[@name='action_payslip_done']" position="after">

## Option 3 (After Create Payment Report):
    <xpath expr="//button[@name='action_payslip_payment_report']" position="after">

## Option 4 (After Print - most reliable fallback):
    <xpath expr="//button[@name='action_payslip_print']" position="after">

## Option 5 (Generic - find any button with string Print):
    <xpath expr="//button[contains(@string,'Print')]" position="after">

## How to find the correct button names:
Run this in Odoo shell:
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    view = env['ir.ui.view'].search([('model','=','hr.payslip'),('type','=','form'),('inherit_id','=',False)], limit=1)
    print(view.arch)
