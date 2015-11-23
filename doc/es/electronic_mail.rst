==================
Correo electrónico
==================

.. inheritref:: electronic_mail/electronic_mail:paragraph:introduccion

**Tryton** nos permite gestionar el envío y recepción de correos electrónicos a través
del sistema para una gestión más eficaz de nuestra correspondencia electrónica.
Podemos llevar así un registro más eficiente de nuestras actividades, evitando posibles
pérdidas de información que se pueden producir cuando la mensajería electrónica
no está integrada en nuestro ERP.

.. inheritref:: electronic_mail/electronic_mail:section:mailbox

Buzón de correo
===============


Los buzones de correo nos permiten agrupar distintos correos para poder
encontrarlos más fácilmente. Son directorios virtuales donde se clasificarán los
correos electrónicos según la configuración que le hayamos dado previamente.

Podemos crear nuevos buzones de correo y acceder a estos de forma más sencilla
por medio del menú |box_menu|, donde nos aparecerán todos los buzones que
vayamos creando. Para crear un buzón, simplemente tenemos que clicar en el botón
*Nuevo* darle un nombre al buzón y permisos de acceso a los usuarios que queramos
y ya tendremos creado un nuevo buzón. Posteriormente configuraremos qué correos se
guardarán en qué buzones.

Correo electrónico
==================

Mediante la ruta |mail_menu| accederemos a un listado de todos los correos
electrónicos. Podremos cambiar la vista y acceder a cada uno de los correos que nos
aparecen en ella. Además, si hemos creado algún buzón, nos aparecerán también en
el menú para poder acceder solo a los correos del buzón en cuestión.

.. inheritref:: electronic_mail/electronic_mail:section:configuracion

Configuración
=============

Antes de la instalación del módulo, debemos asegurarnos que el administrador
del servidor ha especificado la opción ``data_path`` en el fichero de configuración.
Esto es necesario porque los correos generados se guardarán en el subdirectorio
``email`` dentro de éste directorio.

Para que el correo electrónico funcione primero debemos configurarlo desde la
opción de menú: |menu_configuracion|.
Allí podremos seleccionar qué buzones de correo queremos utilizar para las
carpetas básicas.

* **Borrador**: Se guardarán en este buzón aquellos correos de los que no se
  haya finalizado la edición.

* **Salida**: Se guardarán en este buzón los correos que todavía estén
  pendientes de enviar.

* **Enviado**: Se guardarán en este buzón aquellos correos que se hayan
  enviado correctamente.

* **Error**: Se guardarán en este buzón todos aquellos correos en los que se
  ha producido algún error durante el envío del mismo.

.. Note:: Aunque es posible utilizar un único buzón para todas las carpetas
   se recomienda crear un buzón para cada una de ellas para poder diferenciar
   claramente en qué estado está cada uno de los correos.


.. |menu_configuracion| tryref::  electronic_mail.menu_electronic_mail_configuration/complete_name
.. |box_menu| tryref:: electronic_mail.menu_mailbox/complete_name
.. |mail_menu| tryref:: electronic_mail.menu_mail/complete_name
