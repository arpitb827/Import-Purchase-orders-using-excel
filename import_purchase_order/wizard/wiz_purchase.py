from openerp import models,fields,api
from openerp.tools.translate import _
import xlrd
import base64
import os
from datetime import datetime
import time
import tempfile
class wiz_import_purchase_order(models.TransientModel):
    _name = 'wiz.import.purchase.order'
    _description = 'Importer Purchase Orders'
    
    name = fields.Binary(string = 'Import Excel')
    state = fields.Selection([('init','init'),('done','done')], 
        string ='state', readonly=True, default='init')
    filename = fields.Char('Filename')
    
    @api.multi
    def _prepare_order_line(self,product_id=False,plan_dt=False,product_qty=False,partner_id=False,name=False,price_unit=0.0,date_order=False):
        vals={}
        if product_id and plan_dt and product_qty and partner_id :
            vals={
                  'product_id':product_id and product_id.id or False,
                  'date_planned':plan_dt ,
                  'product_uom':product_id and product_id.product_tmpl_id.uom_po_id.id or False,
                  'price_unit':product_id and product_id.product_tmpl_id.standard_price or 0.0,
                  'product_qty':product_qty or 0.0,
                  'state':'draft',
                  'name':name or product_id and product_id.product_tmpl_id.description or product_id.name_template,
                  }
            
        elif plan_dt and product_qty and partner_id and name:
             vals={
                  'date_planned':plan_dt ,
                  'product_uom':product_id and product_id.product_tmpl_id.uom_po_id.id or False,
                  'price_unit':product_id and product_id.product_tmpl_id.standard_price or 0.0,
                  'product_qty':product_qty or 0.0,
                  'state':'draft',
                  'name':name or product_id and product_id.product_tmpl_id.description or product_id.name_template,
                  }
        elif product_qty and partner_id and name:
             vals={
                  'date_planned':date_order,
                  'product_uom':1,
                  'price_unit':price_unit,
                  'product_qty':product_qty or 0.0,
                  'state':'draft',
                  'name':name ,
                  }
        return vals
    
    @api.multi
    def _make_draft_purchase_order(self, partner_id= False, eff_dt= False, location_id=False, 
                                            plan_dt=False, invoice_method=False, company_id=False):
        vals={}
        
        if partner_id and eff_dt and location_id and plan_dt and invoice_method and company_id:
            vals={
                  'partner_id':partner_id and partner_id.id or False,
                  'date_order':eff_dt ,
                  'location_id':location_id and location_id.id or False,
                  'minimum_planned_date':plan_dt,
                  'invoice_method':str(invoice_method),
                  'company_id':company_id and company_id.id or False,
                  'state':'draft',
                  'pricelist_id':partner_id and partner_id.property_product_pricelist_purchase.id or False
                  }
        elif partner_id and eff_dt and location_id and invoice_method and company_id:
            vals={
                  'partner_id':partner_id and partner_id.id or False,
                  'date_order':eff_dt ,
                  'location_id':location_id and location_id.id or False,
                  'minimum_planned_date':lambda *a: time.strftime('%Y-%m-%d'),
                  'invoice_method':str(invoice_method),
                  'company_id':company_id and company_id.id or False,
                  'state':'draft',
                  'pricelist_id':partner_id and partner_id.property_product_pricelist_purchase.id or False
                  }
        elif partner_id and location_id and invoice_method and company_id:
            vals={
                  'partner_id':partner_id and partner_id.id or False,
                  'date_order':lambda *a: time.strftime('%Y-%m-%d') ,
                  'location_id':location_id and location_id.id or False,
                  'minimum_planned_date':lambda *a: time.strftime('%Y-%m-%d'),
                  'invoice_method':str(invoice_method),
                  'company_id':company_id and company_id.id or False,
                  'state':'draft',
                  'pricelist_id':partner_id and partner_id.property_product_pricelist_purchase.id or False
                  }
                    
        return vals
    
    @api.multi
    def create_purchase_orders(self):
        product_product = self.env['product.product']
        stock_location = self.env['stock.location']
        res_partner = self.env['res.partner']
        res_company = self.env['res.company']
        product_product = self.env['product.product']
        product_template = self.env['product.template']
        product_uom = self.env['product.uom']
        purchase_order = self.env['purchase.order']
        filepath = self.env['ir.config_parameter'].get_param('Import Purchase Orders')
        f = tempfile.NamedTemporaryFile(mode='wb+', delete=False)
        filename = '/tmp/' + str(self.filename)
        with open(filename, 'wb') as f:
            x = base64.b64decode(self.name)
            f.write(x)
        wb = xlrd.open_workbook(filename)
        lst = []
        view_ref = self.pool.get('ir.model.data').get_object_reference(self.env.cr,self.env.uid, 'purchase', 'purchase_order_tree')
        view_id = view_ref and view_ref[1] or False
        for s in wb.sheets():
            total_rows = s.nrows 
            partner_id=False
            location_id=False
            company_id=False
            eff_dt = False
            plan_dt = False
            product_id = False
            product_qty = 0.0
            price_unit = 0.0
            name = False
            uom = False
            for row in range(1, s.nrows):
                partner =  s.cell(row,0).value
                date_order = s.cell(row,1).value
                location = s.cell(row,2).value
                planned_date = s.cell(row,3).value
                invoice_method = s.cell(row,4).value
                company = s.cell(row,5).value
                product = s.cell(row,6).value
                product_qty = s.cell(row,7).value
                name = s.cell(row,8).value
                uom = s.cell(row,9).value
                price_unit = s.cell(row,10).value
                if partner :
                    partner_id = res_partner.search([('name','ilike',partner),('supplier','=',True)])
                if company :
                    company_id = res_company.search([('name','=',company)])
                if location:
                    location_id = stock_location.search([('name','=',location),('usage','=','internal'),('company_id','=',company_id.id)])
                if date_order:
                    try :
                        if date_order and isinstance(date_order, (long, int, float)):
                            seconds1 = (date_order - 25569) * 86400.0
                            eff_dt=datetime.utcfromtimestamp(seconds1).strftime('%Y-%m-%d')  
                        elif date_order:
                            serial1=str(date_order)
                            dt1=str(date_order).replace('/','-')
                            dj_date = datetime.strptime(dt1,'%d-%m-%Y')
                            eff_dt=dj_date.strftime('%Y-%m-%d')
                    except :
                        pass
                if planned_date:
                    try :
                        if planned_date and isinstance(planned_date, (long, int, float)):
                            seconds1 = (planned_date - 25569) * 86400.0
                            plan_dt=datetime.utcfromtimestamp(seconds1).strftime('%Y-%m-%d')  
                        elif planned_date:
                            serial1=str(planned_date)
                            dt1=str(planned_date).replace('/','-')
                            dj_date = datetime.strptime(dt1,'%d-%m-%Y')
                            plan_dt=dj_date.strftime('%Y-%m-%d')
                    except :
                        pass
                if product:
                    product_id = product_product.search([('name_template','=',product)])
                if product_uom:
                    uom_id = product_uom
                result = self._make_draft_purchase_order(partner_id, eff_dt, location_id, 
                                                  plan_dt, invoice_method, company_id)
                order_line = self._prepare_order_line(product_id,plan_dt,product_qty,partner_id,name,price_unit,eff_dt)
                result.update({'order_line':[(0,0,order_line)]})
                purchase_order.create(result)

        
        return  {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'res_id': False,
            'view_type': 'form',
            'view_mode': 'tree',
            'view_id': view_id,
            'target': 'current',
            'nodestroy': True,
            
        }