export default function Featured() {
  return (
    <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center min-h-screen px-6 py-12 lg:py-0 bg-white">
      <div className="flex-1 h-[400px] lg:h-[800px] mb-8 lg:mb-0 lg:order-2">
        <img
          src="https://cdn.poehali.dev/projects/d98a14bf-5886-478b-a30d-b53ef7c6d1e0/files/93c39f72-073b-435f-8bc9-d0233d4cb08c.jpg"
          alt="Коллекция премиальных трубок"
          className="w-full h-full object-cover"
        />
      </div>
      <div className="flex-1 text-left lg:h-[800px] flex flex-col justify-center lg:mr-12 lg:order-1">
        <h3 className="uppercase mb-4 text-sm tracking-wide text-neutral-600">Для настоящих ценителей</h3>
        <p className="text-2xl lg:text-4xl mb-8 text-neutral-900 leading-tight">
          Мы отбираем только лучшее — классические трубки, кальяны, зажигалки и расходники от проверенных мировых брендов. Качество, которое чувствуется с первого прикосновения.
        </p>
        <button className="bg-black text-white border border-black px-4 py-2 text-sm transition-all duration-300 hover:bg-white hover:text-black cursor-pointer w-fit uppercase tracking-wide">
          Перейти в каталог
        </button>
      </div>
    </div>
  );
}