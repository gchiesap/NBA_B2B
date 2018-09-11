# -*- coding: utf-8 -*-
"""
Created on Mon Sep 10 17:33:54 2018

@author: gchiesap
"""

import pandas as pd
import source as fp



class costos_class():
	def __init__(self,costos_sac_1,costos_campania_1):
		self.costos_sac = (costos_sac_1).tolist()
		self.costos_campania = (costos_campania_1).tolist()

##Funcion que prepara los datos para el calculo del VAN

def melt_data(base_clientes,of,plataforma,meses):
    
    #FACTURACION CUANDO SE APLICA LA OFERTA
    fact_oferta = fp.fact_t(base_clientes,of,meses)
    ##REEMPLAZAR POR EL CHURN CON OFERTA
    churn_oferta = fp.churn_t(base_clientes,of,meses)
    
    #MELT DE LA TABLA DE CLIENTES

    bcm = pd.melt(base_clientes,id_vars=base_clientes[base_clientes.columns.difference(of['id_oferta'].tolist())].columns,var_name='oferta')
    bcm = bcm.rename(columns={'value':'apto_oferta'})
    
    ##JOIN ENTRE BASE CLIENTES Y LA FACTURACION DE ACA A N MESES DE CADA OFERTA

    lista_ofertas = of['id_oferta'].tolist()
    for oferta in lista_ofertas:
        fact_oferta[oferta]['oferta'] = oferta
    df_fact = pd.DataFrame()
    for oferta in lista_ofertas:
        df_fact = pd.concat([df_fact,fact_oferta[oferta]])

    bcm=bcm.merge(df_fact,on=['ani','oferta'],how='left')
    for i in range(0,meses):
        bcm.rename(columns={i:('fact_'+str(i))},inplace=True)
    
    ##JOIN ENTRE BASE CLIENTES Y EL CHURN DE ACA A N MESES DE CADA OFERTA

    lista_ofertas = of['id_oferta'].tolist()
    for oferta in lista_ofertas:
        churn_oferta[oferta]['oferta'] = oferta
    df_churn = pd.DataFrame()
    for oferta in lista_ofertas:
        df_churn = pd.concat([df_churn,churn_oferta[oferta]])

    bcm=bcm.merge(df_churn,on=['ani','oferta'],how='left')
    for i in range(0,meses):
        bcm.rename(columns={i:('churn_'+str(i))},inplace=True)
    
    
    ##Lista de columnas de churn y facturacion
    churns = []
    facts = []

    for i in range(0,meses):
        churns.append('churn_'+str(i))
        facts.append('fact_'+str(i))
    
    ##Probabilidad de quedarse en el mes N
    for i in range(0,meses):
        if i == 0:
            bcm[churns[i]] = 1-bcm[churns[i]]
        else:
            bcm[churns[i]] = bcm[churns[i-1]]*(1-bcm[churns[i]])
    
    ##Agregacion de aceptacion ofertas
    bcm = pd.merge(bcm,of[['aceptacion_in','aceptacion_out']],left_on='oferta',right_on=of['id_oferta'])
    
    ##Agregacion de Costos de acciones

    costos_in = costos_class(fp.costo_total(of,plataforma)['cost_sac'],fp.costo_total(of,plataforma)['cost_campana_in'])
    costos_out = costos_class(fp.costo_total(of,plataforma)['cost_sac'],fp.costo_total(of,plataforma)['cost_campana_out'])

    costos=pd.DataFrame()
    costos['oferta'] = lista_ofertas
    costos['cost_sac_in'] = costos_in.costos_sac
    costos['cost_sac_out'] = costos_out.costos_sac
    costos['cost_camp_in'] = costos_in.costos_campania
    costos['cost_camp_out'] = costos_in.costos_campania

    bcm = pd.merge(bcm,costos,on='oferta')
    
    
    bc = pd.melt(base_clientes,id_vars=base_clientes[base_clientes.columns.difference(['prob_cater','prob_upsell','prob_digitales','prob_downsell'])].columns,var_name='probs')
    bc = bc[['ani','probs','value']]
    tipo_of = pd.DataFrame()
    tipo_of['oferta'] = of['id_oferta'].tolist()
    tipo_of['probs'] = pd.Series()

    a = tipo_of[tipo_of['oferta'].str.contains('desc_')].index.tolist() 
    tipo_of.loc[a,'probs'] = 'prob_rete'
    a = tipo_of[tipo_of['oferta'].str.contains('upsell_')].index.tolist() 
    tipo_of.loc[a,'probs'] = 'prob_upsell'
    a = tipo_of[tipo_of['oferta'].str.contains('cater_')].index.tolist() 
    tipo_of.loc[a,'probs'] = 'prob_cater'
    a = tipo_of[tipo_of['oferta'].str.contains('ftth_')].index.tolist() 
    tipo_of.loc[a,'probs'] = 'prob_digitales'
    
    tipo_of = tipo_of.merge(bc,on='probs')
    
    tipo_of = tipo_of.rename(columns={'value':'aceptacion'})
    bcm = bcm.merge(tipo_of,on=['ani','oferta'],how='left')
    bcm['aceptacion'] = bcm['aceptacion'].fillna(1)
    
    filtro = bcm[bcm['aceptacion']==1].index.tolist()
    bcm.loc[filtro,'aceptacion'] = (bcm.loc[filtro,'aceptacion_in']+bcm.loc[filtro,'aceptacion_out'])/2
    
    return bcm

##FUNCION QUE CALCULA LA DIFERENCIA ENTRE VAN CON Y SIN ACCION

def calculo_van_diff_2(bcm,meses,canal,interes):
    
    bcm['van_con'] = 0
    bcm['van_sin'] = 0
    
    for i in range(0,meses):
        bcm['van_con'] = (bcm['van_con'] + (((bcm['aceptacion']*bcm['contactabilidad']*bcm['churn_'+str(i)]*
                                           (bcm['fact_'+str(i)]-bcm['costos']-bcm['cost_sac_'+canal]))
                                           +((1-bcm['aceptacion'])*(1-bcm[['churn_calibrated']*(i+1)].prod(axis=1))*
                                             (bcm['fact']-bcm['costos'])))-bcm['cost_camp_'+canal])/(pow(1+interes,i)))
        
    for i in range(0,meses):
        bcm['van_sin'] = (bcm['van_sin'] +(((1-bcm[['churn_calibrated']*(i+1)]).prod(axis=1))*
                                          (bcm['fact']-bcm['costos']))/(pow(1+interes,i)))

    
    bcm['van_diff'] = bcm['van_con']-bcm['van_sin']
    
    return bcm

 ##Hago estrategicas las colas de retencion   
def ofertas_rete(base_clientes,of_rete,años):
    
    base_clientes['años_esperado'] = 1/(base_clientes['churn_calibrated']*0.5)/12
    no_superan = base_clientes['años_esperado'] < años
    umbrales = base_clientes[no_superan]['años_esperado'].max()/len(of_rete)
    indices = of_rete.sort_values(['fact_esp','duracion'],ascending=[True,True]).index
    
    for i in range(0,len(base_clientes['años_esperado'])):
        for k in range(0,len(of_rete)):
            if (base_clientes.loc[i,'años_esperado']>k*umbrales) & (base_clientes.loc[i,'años_esperado']<=k+1*umbrales):
                base_clientes.loc[i,of_rete.loc[indices[k],'id_oferta']] = 2
    
    return base_clientes    

##Hago estrategicas las colas de cater
    
def ofertas_cater(base_clientes):
    cater_of = [col for col in base_clientes.columns if 'cater_' in col]
    for i in range(0,len(base_clientes)):
        if(base_clientes.loc[i,'target_cater'] == 1):
            for k in range(0,len(cater_of)):
                if(base_clientes.loc[i,cater_of[k]]>=1):
                    #Hago esa oferta estrategica
                    base_clientes.loc[i,cater_of[k]] = 2
                    break
    
    return base_clientes

##Hago estrategicas las colas de upsell

def ofertas_upsell(base_clientes):
    upsell_of = [col for col in base_clientes.columns if 'upsell_' in col]
    for i in range(0,len(base_clientes)):
        if(base_clientes.loc[i,'target_upsell'] == 1):
            for k in range(0,len(upsell_of)):
                if(base_clientes.loc[i,upsell_of[k]]>=1):
                    #Hago esa oferta estrategica
                    base_clientes.loc[i,upsell_of[k]] = 2
                    break
    
    return base_clientes

def oferta_cuit(NBA_,umbral):
    cuits = NBA_.columns.str.split('_').str[1].unique()
    ofertas = NBA_.index
    for cuit in cuits:
        df = NBA_.T[NBA_.columns.str.contains('_'+cuit+'_')]
        for oferta in ofertas:
            suma = df[oferta].sum()
            #print('La oferta '+oferta+ ' para el cuit '+cuit+' es '+str(suma))
            while(suma<umbral):
                df[oferta] = df[oferta].replace(df[oferta].min(),0)
                suma = df[oferta].sum()
            #print('La oferta '+oferta+ ' para el cuit '+cuit+' es '+str(suma))
        NBA_.T[NBA_.columns.str.contains('_'+cuit+'_')] = df
    
    return NBA_

##Tabla que arma los podios de cada accion para los diferentes anis
def tabla_ofertas(NBA_,umbral,muestro):

    prioridades = ['ftth_','desc_','upsell_','cater_']
    cuits2 = NBA_['cuit'].tolist()
    cuits = NBA_['cuit'].unique().tolist()
    NBA_['cuit'] = cuits2
    
    podio = []
    total = muestro
    for i in range(0,total):
        podio.append(i+1)
        
    dt1 = pd.DataFrame(columns=podio,index=NBA_.index)
    
    
    
    tipo_ofertas = {}
    for i in range(0,len(prioridades)):
        tipo_ofertas[i] = [col for col in NBA_.columns if prioridades[i] in col]
    
    #Analisis a nivel CUIT
    
    for cuit in cuits:
        df = NBA_[NBA_['cuit']==cuit]
        anis = df.index.tolist()
        
        if(len(df)>1):
            
        ##OFERTA NIVEL CUIT
            for ani in anis:
                lista = []
                ##Primero reviso las estrategicas
                estrategicas = df.T[df.T.values == 'EST'].index.unique().tolist()

                for k in range(0,len(prioridades)):
                    for i in range(0,len(estrategicas)):
                        if(estrategicas[i] in tipo_ofertas[k]):
                            lista.append(estrategicas[i])
                
                of_rete = [col for col in NBA_.columns if 'desc_' in col]
                
                ##Ahora las que no son estrategicas
                estrategicas = estrategicas + ['cuit'] + of_rete
                ##pongo todas las no estrategicas
                a=df[df.columns.difference(estrategicas)].sum()
                b=df[df.columns.difference(estrategicas)].loc[ani]
                tmp = a[a>umbral].sort_values(ascending=False).index.tolist()
                for i in range(0,len(tmp)):
                    if b[b.index == tmp[i]].values[0] == 0:
                        tmp[i] = 'nada'
                
                lista = lista + tmp
                
                superan = len(lista)
                if superan == total:
                    lista = lista 
                elif superan > total:
                    lista = lista[0:total]
                else:
                    lista = lista + ['nada']*(total-superan)
                
                dt1.T[ani] = lista
 
        elif (len(df)==1):
            lista = []
            ##Primero reviso las estrategicas
            estrategicas = df.T[df.T.values == 'EST'].index.unique().tolist()

            for k in range(0,len(prioridades)):
                for i in range(0,len(estrategicas)):
                    if(estrategicas[i] in tipo_ofertas[k]):
                        lista.append(estrategicas[i])

            of_rete = [col for col in NBA_.columns if 'desc_' in col]
            
            ##Ahora las que no son estrategicas
            estrategicas = estrategicas + ['cuit'] + of_rete
            ##pongo todas las no estrategicas
            a=df[df.columns.difference(estrategicas)].sum()
            tmp = a[a>umbral].sort_values(ascending=False).index.tolist()
            
            lista = lista + tmp
                
            superan = len(lista)
            if superan == total:
                lista = lista 
            elif superan > total:
                lista = lista[0:total]
            else:
                lista = lista + ['nada']*(total-superan)
            
            ani = df[df['cuit']==cuit].index.values[0]
            dt1.T[ani] = lista

    
        
    dt1['cuit'] = NBA_['cuit']
    
    return dt1


##Funcion principal del motor

def NBA(base_clientes,of,plataforma,meses,canal,umbral,tasa,muestro):
    
    ##Acondiciono las acciones estrategicas
    
    of_rete = of[of['tipo_oferta']=='descuento']
    base_clientes = ofertas_rete(base_clientes,of_rete,3)
    #base_clientes = ofertas_cater(base_clientes)
    #base_clientes = ofertas_upsell(base_clientes)
    
    ##Acondiciono la base de datos para ser procesada
    bcm = melt_data(base_clientes,of,plataforma,meses)
    
    ##Calculo el van para cada oferta en cada ANI
    bcm = calculo_van_diff_2(bcm,meses,canal,tasa)
    
    NBA_ = bcm.pivot_table(index='ani',columns='oferta',values='van_diff')
    NBA_aptos = bcm.pivot_table(index='ani',columns='oferta',values='apto_oferta')
    
    ##llevo a cero todas las ofertas no aptas
    NBA_[NBA_aptos==0] = 0
    ##llevo a 'EST' todas las ofertas estrategicas
        
    NBA_ = oferta_cuit(NBA_,umbral)
    NBA_[NBA_aptos==2] = 'EST'
    
    NBA_cuit = pd.merge(NBA_,base_clientes[['cuit']],left_on=NBA_.index,right_on=base_clientes['ani'])
    NBA_cuit = NBA_cuit.rename(columns={'key_0':'ani'})
    NBA_cuit = NBA_cuit.set_index('ani')
    
    dt1=tabla_ofertas(NBA_cuit.copy(),umbral,muestro)
    
    
    return [NBA_,NBA_aptos,dt1]