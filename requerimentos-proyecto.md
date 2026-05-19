## Base de datos
### Conexion a la base de datos
La base de datos postgresql se levanto en el cloud Railway y es accesible mediante variables de entorno o la misma CLI de railway. Se levanto especificamente para este proyecto, por ende no tienen ningun complemento ni tablas adicionales solo las bases. Debemos crear una skill para manejar agenticamente la BDD. Debemos activar el plugin de pgvector para el RAG. Todas las migraciones deben ejecutarse desde la maquina local contra la instancia en cloud.
### Diseño de la base de datos
El diseño de la base de datos tiene que ser un script de sql para correrlos desde localhost contra la instancia cloud y debemos guardar la migracion inicial en una carpeta del proyecto con las futuras versiones. 

## ETL
Una de las claves del exito de este proyecto es la correcta vectorizacion de documentos en la base de datos. El backend del back office debe contar con un motor de lectura y transcripcion del PDF a texto/markdown, yo personalmente recomiendo https://github.com/docling-project/docling. Contexto importante: Ya conocemos de antemano los distintos formatos que van a tener los PDFs. Toda la informacion es en base a productos, tenelo en cuenta a la hora de diseñar la base de datos. En principio no me interesa guardar en ningun bucket los PDFs, puede ser una feature a futuro.

## Agente
- Debemos poder trackear las conversaciones y "desiciones" del agente.
- Debemos contar con un sistema de tickets, cuando el agente no sabe una respuesta tenga la opcion de crear una excepcion "No tengo esa info" + "Ticket al sistema"
- "El agente SOLO habla de documentos validados." Esto significa que debe referenciar en todo momento que documento contiene esa informacion (campo que debe tomar de los metadatos del RAG). La similitud se persiste en `agent_decisions` para auditoria interna; el mensaje al RTC solo cita el titulo del documento en el bloque Fuentes.
- Solo responde a RTCs en sistema. Esto significa que debe haber una tabla de usuarios habilitados por numero de telefono donde el agente habilita a quien responde y a quien no.


## Back Office
- Dashboard de analiticas (heatmap de conocimiento, gaps, uso por pais, tiempo promedio de respuesta )
- En el front debemos poder cargar un PDF y clasificarlo como (esperar reunion del martes) 
- Accesos a carga y descarga de archivos + RAG: Los cientificos deben poder cargar los archivos y los RTC consultarlos. No me interesa guardarlos en principio pero si que se pueda ver desde la web la transcripcion a markdown luego de pasar por docling.
- Escalabilidad regional - tener en cuenta desde el inicio. Los documentos pueden ser de alcance global o regional (pais). Se deberia poder filtrar por metadata el pais de origen, y ver que paises tiene habilitado a consultar el comercial que se comunica con el agente.
- Te deja editar el sistem prompt desde la base de datos (mostrar en la web)
- Roles y permisos + Logs de edicion 
- Ver el Sistema de tickets que levanta el agente cuando "no sabe algo" o "no encuentra algo"